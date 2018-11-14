extern crate artparser;

use artparser::{ArtFile, ArtError};
use std::env::{args};

fn main() -> Result<(), ArtError> {
    let argv: Vec<String> = args().collect();
    let fname = argv.get(1).map(|s|s.as_str()).unwrap_or("examples/empty.art");
    let result = ArtFile::from_path(fname)?;
    println!("pins: {:?}", result.pins);
    println!("layers: {:?}", result.layers);
    println!("actions: {:?}", result.actions);
    Ok(())
}
