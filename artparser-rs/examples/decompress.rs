extern crate artparser;
extern crate byteorder;

use self::byteorder::{ByteOrder, LittleEndian};
use artparser::{decompress};
use std::fs::{File};
use std::io::{self, Read, Write};
use std::io::Result;

fn can_fail() -> Result<()> {
    let mut fd = File::open("examples/empty.art")?;
    let mut header = vec![0u8; 0x28];
    fd.read_exact(&mut header)?;
    let len = LittleEndian::read_u32(&header[0x24..0x28]) as usize;
    let mut compressed = vec![0u8; len];
    fd.read_exact(&mut compressed)?;
    let decompressed = decompress(&compressed).expect("couldn't decompress");
    io::stdout().write(&decompressed)?;
    Ok(())
}

fn main() {
    can_fail().unwrap();
}
