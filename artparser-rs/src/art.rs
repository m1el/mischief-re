use std::{
    io::{self, Read},
    fs::File,
    path::Path,
};

use lzunpack::{decompress, DecodeError};
use parser::{read_compressed, read_content};

pub struct ArtFile {
    pub version: usize,
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
    pub actions: Vec<(usize, Action)>,
}

impl ArtFile {
    pub fn from_path<P: AsRef<Path>>(path: P) -> Result<ArtFile, ArtError> {
        let mut buf = Vec::new();
        let mut file = File::open(path)?;
        file.read_to_end(&mut buf)?;
        ArtFile::from_bytes(&buf[..])
    }
    pub fn from_bytes(bytes: &[u8]) -> Result<ArtFile, ArtError> {
        let (compressed, (_ver, pins, _rest_len)) = read_compressed(bytes)
            .map_err(|_e| ArtError::ParsingError(String::from("failed parse compressed")))?;

        let decompressed = decompress(compressed)?;

        let (_, mut art) = read_content(&decompressed[..])
            .map_err(|_e| ArtError::ParsingError(String::from("failed parse decompressed")))?;

        art.pins = pins;

        Ok(art)
    }
}

#[derive(Debug)]
pub struct RGB {
    pub r: u8,
    pub g: u8,
    pub b: u8,
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

#[derive(Debug)]
pub struct ArtPin {
    pub matrix: [f32; 16],
    pub name: String,
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

pub struct Image {
    pub kind: u32,
    pub raw: Vec<u8>,
}

#[derive(Debug)]
pub enum Action {
    Stroke { points: Vec<StrokePoint> },
    _Unknown08(u32),
    PenTransform { matrix: [f32; 16], zoom: f32 },
    PenProperties(PenUpdate),
    PenColor(RGB),
    PenIsEraser(bool),
    PasteLayer(PasteProps),
    LayerTransform { matrix: [f32; 16], zoom: f32 },
    CutRect { rect: [f32; 4] },
    LayerMerge {
        other: usize,
        opacity_src: f32, opacity_dst: f32,
        matrix: [f32; 16], zoom: f32,
    },
    DrawImage {
        dst_center: [f32; 2],
        dst_size: [f32; 2],
        _unknown: u32,
        src_size: [u32; 2],
        image_id: usize,
    },
    _Unknown05([u8;0x14]),
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
    pub from_layer: usize,
    pub rect: [f32; 4],
    pub matrix1: [f32; 16],
    pub zoom1: f32,
    pub matrix2: [f32; 16],
    pub zoom2: f32,
}

#[derive(Debug)]
pub enum ArtError {
    ParsingError(String),
    IoError(io::Error),
    //FromUtf8Error(FromUtf8Error),
    //Utf8Error(Utf8Error),
    DecompressError(DecodeError),
    //BadMagic(u32),
    //BadVersion(u32),
    //BadAction(u32),
}
impl From<io::Error> for ArtError {
    fn from(err: io::Error) -> ArtError { ArtError::IoError(err) }
}
//impl From<FromUtf8Error> for ArtError {
//    fn from(err: FromUtf8Error) -> ArtError { ArtError::FromUtf8Error(err) }
//}
//impl From<Utf8Error> for ArtError {
//    fn from(err: Utf8Error) -> ArtError { ArtError::Utf8Error(err) }
//}
impl From<DecodeError> for ArtError {
    fn from(err: DecodeError) -> ArtError { ArtError::DecompressError(err) }
}
