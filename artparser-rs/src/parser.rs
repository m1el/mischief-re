use nom::{
    IResult,
    ToUsize,
    branch::{alt},
    bytes::complete::{tag, take},
    combinator::{map, rest_len},
    error::{ErrorKind, ParseError, VerboseError},
    number::complete::{le_u8, le_u32, le_f32},
    multi::{count, length_data, length_value},
    sequence::{preceded, tuple},
};

use art::*;

fn length_count<I, O, E, N, C, F>(
    c: C,
    f: F,
) -> impl Fn(I) -> IResult<I, Vec<O>, E>
where
    I: Clone + PartialEq,
    N: ToUsize,
    C: Fn(I) -> IResult<I, N, E>,
    F: Fn(I) -> IResult<I, O, E>,
    E: ParseError<I>,
{
    move |i: I| {
        let mut input = i.clone();

        let (i, count) = c(input.clone())?;
        input = i.clone();

        let mut res = Vec::new();

        for _ in 0..count.to_usize() {
            let input_ = input.clone();
            match f(input_) {
                Ok((i, o)) => {
                    res.push(o);
                    input = i;
                }
                Err(nom::Err::Error(e)) => {
                    return Err(nom::Err::Error(E::append(i, ErrorKind::Count, e)));
                }
                Err(e) => {
                    return Err(e);
                }
            }
        }

        Ok((input, res))
    }
}

pub fn read_compressed<'a>(i: &'a[u8])
-> IResult<&'a[u8], (usize, Vec<ArtPin>, usize), VerboseError<&'a[u8]>>
{
    let ver00 = map(tuple((tag(b"\x00\x00\x00\x00"), take(0x08_u8))),
                    |_| (0x00_usize, Vec::new()));
    let ver81 = map(tuple((tag(b"\x81\x00\x00\x00"), take(0x1c_u8))),
                    |_| (0x81_usize, Vec::new()));
    let ver82 = map(tuple((tag(b"\x82\x00\x00\x00"), take(0x21_u8),
                          length_count(le_u32, read_pin))),
                    |t| (0x82_usize, t.2));

    let file = tuple((
        alt((tag(b"\xc5\xb3\x8b\xe7"), tag(b"\xc5\xb3\x8b\xe9"))),
        alt((ver00, ver81, ver82)),
        le_u32,
    ));

    map(file, |(_, (ver, pins), len)| {
        (ver, pins, len.to_usize())
    })(i)
}

pub fn read_content<'a>(i: &'a[u8])
-> IResult<&'a[u8], ArtFile, VerboseError<&'a[u8]>>
{
    let file = tuple((
        le_u32,
        le_u32,
        le_u32,
        read_rgb,
        le_f32,
        le_u32, le_u32, le_u32, le_u32,
        read_pen,
        le_u32, le_u32,
        read_matrix,
        le_f32,
        length_count(le_u32, map(le_u32, |t|t.to_usize())),
        length_count(le_u32, read_layer_info),
        length_count(le_u32, read_image),
        length_count(le_u32, read_action),
        rest_len,
    ));

    map(file, |t| {
        ArtFile {
            version: t.0.to_usize(),
            active_layer: t.1.to_usize(),
            background_color: t.3,
            background_alpha: t.4,
            pen_info: t.9,
            view_matrix: t.12,
            view_zoom: t.13,
            pins: Vec::new(),
            layer_order: t.14,
            layers: t.15,
            images: t.16,
            actions: t.17,
        }
    })(i)
}

fn read_matrix<'a>(i: &'a[u8])
-> IResult<&'a[u8], [f32; 16], VerboseError<&'a[u8]>>
{
    map(count(le_f32, 16), |v| {
        let mut m = [0.0_f32; 16];
        m.copy_from_slice(&v[..]);
        m
    })(i)
}

fn read_rect<'a>(i: &'a[u8])
-> IResult<&'a[u8], [f32; 4], VerboseError<&'a[u8]>>
{
    map(tuple((le_f32, le_f32, le_f32, le_f32)),
        |t| [t.0, t.1, t.2, t.3]
    )(i)
}

fn read_rgb<'a>(i: &'a[u8])
-> IResult<&'a[u8], RGB, VerboseError<&'a[u8]>>
{
    map(tuple((le_u8, le_u8, le_u8)), |t| {
        RGB {
            r: t.0,
            g: t.1,
            b: t.2,
        }
    })(i)
}

fn read_pen<'a>(i: &'a[u8])
-> IResult<&'a[u8], PenInfo, VerboseError<&'a[u8]>>
{
    map(tuple((le_u32, read_rgb, le_f32, le_f32,
               le_f32, le_f32,   le_f32, le_u32)),
        |t| PenInfo {
            kind: t.0,
            color: t.1,
            noise: t.2,
            size: t.3,
            size_min: t.4,
            opacity: t.5,
            opacity_min: t.6,
            is_eraser: t.7 != 0,
        }
    )(i)
}

fn read_pin<'a>(i: &'a[u8])
-> IResult<&'a[u8], ArtPin, VerboseError<&'a[u8]>>
{
    map(tuple((read_matrix, read_str)), |(matrix, name)| {
        ArtPin { matrix, name: name.trim().to_string() }
    })(i)
}

fn read_str<'a>(i: &'a[u8])
-> IResult<&'a[u8], &'a str, VerboseError<&'a[u8]>>
{
    length_value(le_u32, |i| Ok((b"", std::str::from_utf8(i).expect("couldn't read str?"))))(i)
}

fn read_const_str<'a>(i: &'a[u8])
-> IResult<&'a[u8], &'a str, VerboseError<&'a[u8]>>
{
    map(take(256_usize), |buf: &[u8]| {
        let start = buf.split(|&c| c == 0).next().unwrap();
        std::str::from_utf8(&start).expect("couldn't read const str?")
    })(i)
}

fn read_layer_info<'a>(i: &'a[u8])
-> IResult<&'a[u8], LayerInfo, VerboseError<&'a[u8]>>
{
    map(tuple((le_u32, le_f32, read_const_str, le_u32, read_matrix, le_f32)), |t| {
        LayerInfo {
            visible: t.0 != 0,
            opacity: t.1,
            name: t.2.to_string(),
            action_count: t.3,
            matrix: t.4,
            zoom: t.5,
        }
    })(i)
}

fn read_image<'a>(i: &'a[u8])
-> IResult<&'a[u8], Image, VerboseError<&'a[u8]>>
{
    map(tuple((le_u32, length_data(le_u32))), |(kind, slice)| {
        Image { kind, raw: slice.to_vec() }
    })(i)
}

fn read_action<'a>(i: &'a[u8])
-> IResult<&'a[u8], (usize, Action), VerboseError<&'a[u8]>>
{
    tuple((
        map(le_u32, |i|i.to_usize()),
        alt((
            read_action_stroke,
            read_action_05,
            read_action_08,
            read_action_pen_transform,
            read_action_pen_props,
            read_action_pen_color,
            read_action_pen_is_eraser,
            read_action_paste_layer,
            read_action_layer_transform,
            read_action_cut_rect,
            read_action_layer_merge,
            read_action_draw_image,
        ))
    ))(i)
}

fn read_action_stroke<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    let (mut input, count) = preceded(tag(b"\x01\x00\x00\x00"), le_u32)(i)?;
    let mut points = Vec::new();
    if count > 0 {
        let (i, mut point) = map(tuple((le_f32, le_f32, le_f32)), |t| {
            StrokePoint { x: t.0, y: t.1, p: t.2 }
        })(input)?;
        input = i;

        points.push(point.clone());
        for _ in 0..count-1 {
            let (i, (tmp32, tmp8)) = tuple((le_u32, le_u8))(input)?;
            input = i;

            let dx = (tmp32 & 0x3fff) as f32 *
                if tmp32 & (1<<14) == 0 { 1.0 } else { -1.0 };
            let dy = ((tmp32 >> 15) & 0x3fff) as f32 *
                if tmp32 & (1<<20) == 0 { 1.0 } else { -1.0 };
            let p = ((tmp32 >> 30) | ((tmp8 as u32) << 2)) as f32;
            point.x += dx / 32.0;
            point.y += dy / 32.0;
            point.p = p / 1023.0;
            points.push(point.clone());
        }
    }
    Ok((input, Action::Stroke { points }))
}

fn read_action_pen_transform<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x33\x00\x00\x00"),
        map(tuple((read_matrix, le_f32)),
            |(matrix, zoom)| Action::PenTransform { matrix, zoom })
    )(i)
}

fn read_action_pen_props<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x34\x00\x00\x00"),
        map(tuple((le_u32, le_f32, le_f32, le_f32, le_f32, le_f32)),
            |t| Action::PenProperties(PenUpdate {
                kind: t.0,
                noise: t.1,
                size: t.2,
                size_min: t.3,
                opacity: t.4,
                opacity_min: t.5,
            }))
    )(i)
}

fn read_action_pen_color<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x35\x00\x00\x00"),
        map(read_rgb, Action::PenColor)
    )(i)
}

fn read_action_pen_is_eraser<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x36\x00\x00\x00"),
        map(le_u32, |v| Action::PenIsEraser(v != 0))
    )(i)
}

fn read_action_paste_layer<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x0f\x00\x00\x00"),
        map(tuple((le_u32, read_rect,
                   read_matrix, le_f32,
                   read_matrix, le_f32)),
            |t| Action::PasteLayer(PasteProps {
                from_layer: t.0.to_usize(),
                rect: t.1,
                matrix1: t.2,
                zoom1: t.3,
                matrix2: t.4,
                zoom2: t.5,
            }))
    )(i)
}

fn read_action_layer_transform<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x0d\x00\x00\x00"),
        map(tuple((read_matrix, le_f32)),
            |(matrix, zoom)| Action::LayerTransform {
                matrix, zoom,
            })
    )(i)
}

fn read_action_cut_rect<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x0e\x00\x00\x00"),
        map(read_rect, |rect| Action::CutRect { rect })
    )(i)
}

fn read_action_layer_merge<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x0c\x00\x00\x00"),
        map(tuple((le_u32, le_f32, le_f32,
                    read_matrix, le_f32)),
            |t| Action::LayerMerge {
                other: t.0.to_usize(),
                opacity_src: t.1,
                opacity_dst: t.2,
                matrix: t.3,
                zoom: t.4,
            })
    )(i)
}

fn read_action_draw_image<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x07\x00\x00\x00"),
        map(tuple((le_f32, le_f32, le_f32, le_f32,
                   le_u32, le_u32, le_u32, le_u32)),
            |t| Action::DrawImage {
                dst_center: [t.0, t.1],
                dst_size: [t.2, t.3],
                _unknown: t.4,
                src_size: [t.5, t.6],
                image_id: t.7.to_usize(),
            })
    )(i)
}

fn read_action_05<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x05\x00\x00\x00"),
        map(take(0x14_usize), |t| {
            let mut buf = [0_u8; 0x14];
            buf.copy_from_slice(t);
            Action::_Unknown05(buf)
        })
    )(i)
}

fn read_action_08<'a>(i: &'a[u8])
-> IResult<&'a[u8], Action, VerboseError<&'a[u8]>>
{
    preceded(
        tag(b"\x08\x00\x00\x00"),
        map(le_u32, Action::_Unknown08)
    )(i)
}
