use std::io::{self, Cursor, Read};
use std::fs::{File};
use std::path::{Path};
use byteorder::{ReadBytesExt, LittleEndian};
use std::string::{FromUtf8Error};
use std::str::{Utf8Error};
use lzunpack::{DecodeError, decompress};

const ART_MAGICS: &[u32] = &[
    0xe78bb3c5, // hex c5b38be7
    0xe98bb3c5, // hex c6b38be9
];

pub struct ArtFile {
    pub version: u32,
    pub active_layer: usize,
    pub background_color: RGB,
    pub background_alpha: f32,
    pub pen_info: PenInfo,
    pub view_matrix: [f32; 16],
    pub view_zoom: f32,
    pub pins: Vec<ArtPin>,
    pub layer_order: Vec<usize>,
    pub layers: Vec<LayerInfo>,
    pub images: Vec<Image>,
    pub actions: Vec<Action>,
}

impl ArtFile {
    pub fn from_path<P: AsRef<Path>>(path: P) -> Result<ArtFile, ArtError> {
        ArtFile::from_input(&mut File::open(path)?)
    }

    pub fn from_input<R: Read>(input: &mut R) -> Result<ArtFile, ArtError> {
        let mut version_header = [0_u8; 8];
        input.read_exact(&mut version_header[..])?;

        let cursor = &mut &version_header[..];
        let magic = read_u32(cursor)?;
        let version = read_u32(cursor)?;
        if !ART_MAGICS.contains(&magic) {
            return Err(ArtError::BadMagic(magic));
        }

        let pins;
        if version & 0xFF == 0 {
            let mut header = vec![0_u8; 0x08];
            input.read_exact(&mut header)?;
            pins = Vec::new();
        } else if version == 0x81 {
            let mut header = vec![0_u8; 0x1c];
            input.read_exact(&mut header)?;
            pins = Vec::new();
        } else if version == 0x82 {
            let mut header = vec![0_u8; 0x21];
            input.read_exact(&mut header)?;
            pins = read_pins(input)?;
        } else {
            return Err(ArtError::BadVersion(version));
        }

        let raw_size = read_u32(input)?;
        let mut compressed = vec![0_u8; raw_size as usize];
        input.read_exact(&mut compressed)?;

        let decompressed = decompress(&compressed)?;
        let cursor = &mut Cursor::new(&decompressed[..]);

        let version = read_u32(cursor)?;
        let active_layer = read_u32(cursor)? as usize;
        let _unknown08 = read_u32(cursor)?;
        let background_color = read_rgb(cursor)?;
        let background_alpha = read_f32(cursor)?;
        let _unknown13 = read_u32(cursor)?;
        let _unknown17 = read_u32(cursor)?;
        let _unknown1b = read_u32(cursor)?;
        let _unknown1f = read_u32(cursor)?;
        let pen_info = read_pen_info(cursor)?;
        let _unknown42 = read_u32(cursor)?;
        let _unknown46 = read_u32(cursor)?;
        let view_matrix = read_matrix(cursor)?;
        let view_zoom = read_f32(cursor)?;

        let order_count = read_u32(cursor)?;
        let mut layer_order = Vec::new();
        for _ in 0..order_count {
            layer_order.push(read_u32(cursor)? as usize);
        }

        let layer_count = read_u32(cursor)?;
        let mut layers = Vec::new();
        for _ in 0..layer_count {
            layers.push(read_layer_info(cursor)?);
        }

        let image_count = read_u32(cursor)?;
        let mut images = Vec::new();
        for _ in 0..image_count {
            images.push(read_image(cursor)?);
        }

        let action_count = read_u32(cursor)?;
        let mut actions = Vec::new();
        for _ in 0..action_count {
            actions.push(read_action(cursor)?);
        }

        Ok(ArtFile {
            version,
            active_layer,
            background_color,
            background_alpha,
            pen_info,
            view_matrix,
            view_zoom,
            pins,
            layer_order,
            layers,
            images,
            actions,
        })
    }
}

#[derive(Debug)]
pub enum ArtError {
    IoError(io::Error),
    FromUtf8Error(FromUtf8Error),
    Utf8Error(Utf8Error),
    DecompressError(DecodeError),
    BadMagic(u32),
    BadVersion(u32),
    BadAction(u32),
}
impl From<io::Error> for ArtError {
    fn from(err: io::Error) -> ArtError { ArtError::IoError(err) }
}
impl From<FromUtf8Error> for ArtError {
    fn from(err: FromUtf8Error) -> ArtError { ArtError::FromUtf8Error(err) }
}
impl From<Utf8Error> for ArtError {
    fn from(err: Utf8Error) -> ArtError { ArtError::Utf8Error(err) }
}
impl From<DecodeError> for ArtError {
    fn from(err: DecodeError) -> ArtError { ArtError::DecompressError(err) }
}

fn read_u8<R: Read>(input: &mut R) -> Result<u8, ArtError> {
    let buf = &mut [0_u8];
    input.read_exact(buf)?;
    Ok(buf[0])
}

fn read_u32<R: Read>(input: &mut R) -> Result<u32, ArtError> {
    Ok(input.read_u32::<LittleEndian>()?)
}

fn read_f32<R: Read>(input: &mut R) -> Result<f32, ArtError> {
    Ok(input.read_f32::<LittleEndian>()?)
}

fn read_rect<R: Read>(input: &mut R) -> Result<[f32; 4], ArtError> {
    let mut rect = [0.0; 4];
    for idx in 0..4 {
        rect[idx] = read_f32(input)?;
    }

    Ok(rect)
}

fn read_matrix<R: Read>(input: &mut R) -> Result<[f32; 16], ArtError> {
    let mut matrix = [0.0; 16];
    for idx in 0..16 {
        matrix[idx] = read_f32(input)?;
    }

    Ok(matrix)
}

fn read_const_string<R: Read>(input: &mut R) -> Result<String, ArtError> {
    let mut buf = [0_u8; 256];
    input.read_exact(&mut buf)?;
    let start = buf[..].split(|&c| c == 0).next().unwrap();
    Ok(std::str::from_utf8(&start)?.to_string())
}

fn read_string<R: Read>(input: &mut R) -> Result<String, ArtError> {
    let count = read_u32(input)?;
    let mut buf = vec![0_u8; count as usize];
    input.read_exact(&mut buf)?;
    println!("{:?}", buf);
    let mut rv = String::from_utf8(buf)?;
    rv.pop();
    Ok(rv)
}

#[derive(Debug)]
pub struct ArtPin {
    pub matrix: [f32; 16],
    pub name: String,
}

fn read_pins<R: Read>(input: &mut R) -> Result<Vec<ArtPin>, ArtError> {
    let count = read_u32(input)?;
    let mut pins = Vec::with_capacity(count as usize);

    for _ in 0..count {
        let matrix = read_matrix(input)?;
        let name = read_string(input)?.trim().to_string();
        pins.push(ArtPin { matrix, name });
    }

    Ok(pins)
}

#[derive(Debug)]
pub struct RGB {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

fn read_rgb<R: Read>(input: &mut R) -> Result<RGB, ArtError> {
    let mut buf = [0_u8; 3];
    input.read_exact(&mut buf[..])?;
    Ok(RGB {
        r: buf[0],
        g: buf[1],
        b: buf[2],
    })
}

#[derive(Debug)]
pub struct PenInfo {
    pub kind: u32,
    pub color: RGB,
    pub noise: f32,
    pub size: f32,
    pub size_min: f32,
    pub opacity: f32,
    pub opacity_min: f32,
    pub is_eraser: bool,
}

fn read_pen_info<R: Read>(input: &mut R) -> Result<PenInfo, ArtError> {
    Ok(PenInfo {
        kind: read_u32(input)?,
        color: read_rgb(input)?,
        noise: read_f32(input)?,
        size: read_f32(input)?,
        size_min: read_f32(input)?,
        opacity: read_f32(input)?,
        opacity_min: read_f32(input)?,
        is_eraser: read_u32(input)? != 0,
    })
}

#[derive(Debug)]
pub struct LayerInfo {
    pub visible: bool,
    pub opacity: f32,
    pub name: String,
    pub action_count: u32,
    pub matrix: [f32; 16],
    pub zoom: f32,
}

fn read_layer_info<R: Read>(input: &mut R) -> Result<LayerInfo, ArtError> {
    Ok(LayerInfo {
        visible: read_u32(input)? != 0,
        opacity: read_f32(input)?,
        name: read_const_string(input)?,
        action_count: read_u32(input)?,
        matrix: read_matrix(input)?,
        zoom: read_f32(input)?,
    })
}

pub struct Image {
    pub kind: u32,
    pub raw: Vec<u8>,
}

fn read_image<R: Read>(input: &mut R) -> Result<Image, ArtError> {
    let kind = read_u32(input)?;
    let size = read_u32(input)?;
    let mut raw = vec![0_u8; size as usize];
    input.read_exact(&mut raw)?;
    Ok(Image { kind, raw })
}

#[derive(Debug)]
pub enum Action {
    Stroke { layer: usize, points: Vec<StrokePoint> },
    _Unknown08(u32),
    PenTransform { matrix: [f32; 16], zoom: f32 },
    PenProperties(PenUpdate),
    PenColor(RGB),
    PenIsEraser(bool),
    PasteLayer(PasteProps),
    LayerTransform { layer: usize, matrix: [f32; 16], zoom: f32 },
    CutRect { layer: usize, rect: [f32; 4] },
    LayerMerge {
        layer: usize, other: usize,
        opacity_src: f32, opacity_dst: f32,
        matrix: [f32; 16], zoom: f32,
    },
    DrawImage {
        layer: usize,
        dst_center: [f32; 2],
        dst_size: [f32; 2],
        _unknown: u32,
        src_size: [u32; 2],
        image_id: usize,
    },
    _Unknown05([u8;0x14]),
}

fn read_action<R: Read>(input: &mut R) -> Result<Action, ArtError> {
    let layer = read_u32(input)? as usize;
    let action_tag = read_u32(input)?;
    let rv = match action_tag {
        0x01 => {
            let mut points = Vec::new();
            let count = read_u32(input)?;
            if count > 0 {
                let mut point = StrokePoint {
                    x: read_f32(input)?,
                    y: read_f32(input)?,
                    p: read_f32(input)?,
                };
                points.push(point.clone());
                for _ in 0..count-1 {
                    let tmp = read_u32(input)?;
                    let byte = read_u8(input)?;
                    let dx = (tmp & 0x3fff) as f32 *
                        if tmp & (1<<14) == 0 { 1.0 } else { -1.0 };
                    let dy = ((tmp >> 15) & 0x3fff) as f32 *
                        if tmp & (1<<20) == 0 { 1.0 } else { -1.0 };
                    let p = ((tmp >> 30) | ((byte as u32) << 2)) as f32;
                    point.x += dx / 32.0;
                    point.y += dy / 32.0;
                    point.p = p / 1023.0;
                    points.push(point.clone());
                }
            }
            Action::Stroke { layer, points }
        },
        0x08 => Action::_Unknown08(read_u32(input)?),
        0x33 => Action::PenTransform {
            matrix: read_matrix(input)?,
            zoom: read_f32(input)?
        },
        0x34 => Action::PenProperties(PenUpdate{
            kind: read_u32(input)?,
            noise: read_f32(input)?,
            size: read_f32(input)?,
            size_min: read_f32(input)?,
            opacity: read_f32(input)?,
            opacity_min: read_f32(input)?,
        }),
        0x35 => Action::PenColor(read_rgb(input)?),
        0x36 => Action::PenIsEraser(read_u32(input)? != 0),
        0x0f => Action::PasteLayer(PasteProps {
            to_layer: layer,
            from_layer: read_u32(input)? as usize,
            rect: read_rect(input)?,
            matrix1: read_matrix(input)?,
            zoom1: read_f32(input)?,
            matrix2: read_matrix(input)?,
            zoom2: read_f32(input)?,
        }),
        0x0d => Action::LayerTransform {
            layer: layer,
            matrix: read_matrix(input)?,
            zoom: read_f32(input)?,
        },
        0x0e => Action::CutRect {
            layer: layer,
            rect: read_rect(input)?,
        },
        0x0c => Action::LayerMerge {
            layer: layer,
            other: read_u32(input)? as usize,
            opacity_src: read_f32(input)?,
            opacity_dst: read_f32(input)?,
            matrix: read_matrix(input)?,
            zoom: read_f32(input)?,
        },
        0x07 => Action::DrawImage {
            layer: layer,
            dst_center: [read_f32(input)?, read_f32(input)?],
            dst_size: [read_f32(input)?, read_f32(input)?],
            _unknown: read_u32(input)?,
            src_size: [read_u32(input)?, read_u32(input)?],
            image_id: read_u32(input)? as usize,
        },
        0x05 => {
            let mut buf = [0_u8; 0x14];
            input.read_exact(&mut buf[..])?;
            Action::_Unknown05(buf)
        },
        _ => return Err(ArtError::BadAction(action_tag)),
    };
    Ok(rv)
}

#[derive(Clone, Debug)]
pub struct StrokePoint {
    pub x: f32,
    pub y: f32,
    pub p: f32,
}

#[derive(Debug)]
pub struct PenUpdate {
    pub kind: u32,
    pub noise: f32,
    pub size: f32,
    pub size_min: f32,
    pub opacity: f32,
    pub opacity_min: f32,
}

#[derive(Debug)]
pub struct PasteProps {
    pub to_layer: usize,
    pub from_layer: usize,
    pub rect: [f32; 4],
    pub matrix1: [f32; 16],
    pub zoom1: f32,
    pub matrix2: [f32; 16],
    pub zoom2: f32,
}
