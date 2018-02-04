extern crate byteorder;

use ::std::cmp::{min};
use self::byteorder::{ByteOrder, LittleEndian, BigEndian};

#[derive(Debug)]
pub enum DecodeError {
    ReferencingEmpty = 1,
    NegativeDistance = 3,
    OutputTooBig = 4,
}

const MRU_DEPTH: usize = 4;
struct MRUList {
    buf: [usize; MRU_DEPTH],
}

impl MRUList {
    #[inline]
    pub fn new() -> MRUList {
        MRUList {
            buf: [0; MRU_DEPTH],
        }
    }

    #[inline]
    pub fn push(&mut self, val: usize) {
        for i in (0..MRU_DEPTH - 1).rev() {
            self.buf[i+1] = self.buf[i];
        }
        self.buf[0] = val;
    }

    #[inline]
    pub fn get_recent(&self) -> usize {
        return self.buf[0];
    }

    #[inline]
    pub fn get_at(&mut self, pos: usize) -> usize {
        assert!(pos < MRU_DEPTH, "MRU get_at position out of range");
        let val = self.buf[pos];
        for i in (0..pos).rev() {
            self.buf[i+1] = self.buf[i];
        }
        self.buf[0] = val;
        let val = self.buf[pos];
        return val;
    }
}

struct ArithDecoder<'a> {
    input: &'a[u8],
    scale: u32,
    value: u32,
    thresholds: Vec<u16>,
}

// context allocation map:
// 0..BF: decision literal/reference
// C0/CC/D8/E4: (12 each) unary code (new distance/mru[0]/mru[1]/mru[2]/mru[3])
// F0..1AF: decision: single-byte-copy shortcut on mru[0]
// 1B0..331: distance decoding
//   1B0:      unallocated
//   1B0..1EF: coarse distance info
//   2B0:      last bit for distance 4/5
//   2B1:      last bit for distance 6/7
//   2B2..2B4: last bits for distances 8..B
//   2B5..2B7: last bits for distances C..F
//   2B8..2BE: last bits for distances 10..17
//   2BF..2C5: last bits for distances 18..1F
//   2C6..2D4: last bits for distances 20..2F
//   2D5..2E3: last bits for distances 30..3F
//   2E4..302: last bits for distances 40..5F
//   303..321: last bits for distances 60..7F
//   322..331: last bits for distances >= 0x80
// 332..735: length decoding
//   332..533: length context collection (new distance)
//     332/333:   unary coded length range (0..7/8..F/10..10F)
//     334..373:  4 collections for length 0..7 (first entry in each collection unallocated)
//     374..3B3:  unallocated
//     3B4..3F3:  4 collections for length 8..F (first entry in each collection unallocated)
//     3F4..433:  unallocated
//     434..533:  length 10..10F (first entry unallocated)
//   534: length context collection (known distance)
//     details like 332..533
// 736..1F35: literal contexts (8 areas of 3 areas of 0x100 contexts)

impl<'a> ArithDecoder<'a> {
    /// Construct an arithmetic decoder for given input
    #[inline]
    pub fn new(input: &'a[u8]) -> ArithDecoder<'a> {
        let value = BigEndian::read_u32(input);
        ArithDecoder {
            input: &input[4..],
            scale: 0xFFFFFFFF,
            value: value,
            thresholds: vec![0x400; 0x1F36],
        }
    }

    /// Read next byte from the input
    #[inline]
    pub fn next_byte(&mut self) -> u8 {
        let val = self.input[0];
        self.input = &self.input[1..];
        val
    }

    /// LZ77 renormalize
    #[inline]
    pub fn renormalize(&mut self) {
        if self.scale < 0x01000000 {
            self.scale = self.scale.wrapping_shl(8);
            self.value = self.value.wrapping_shl(8) | self.next_byte() as u32;
        }
    }

    pub fn get_bit(&mut self, context_idx: usize) -> usize {
        self.renormalize();
        let threshold = self.thresholds[context_idx];
        let scaled_threshold = (self.scale >> 0x0b) * (threshold as u32);

        if self.value < scaled_threshold {
            self.thresholds[context_idx] = (threshold - ((threshold+0x1f) >> 5)) + 0x40;
            self.scale = scaled_threshold;
            return 0;
        } else {
            self.thresholds[context_idx] = threshold - (threshold >> 5);
            self.value -= scaled_threshold;
            self.scale -= scaled_threshold;
            return 1;
        }
    }

    pub fn get_n_bits(&mut self, n: usize, context_base: usize) -> usize {
        let mut value: usize = 0;
        for idx in 0..n {
            let bit = self.get_bit(context_base + (1 << idx) + value);
            value = (value << 1) + bit;
        }
        return value;
    }

    pub fn get_n_bits_flipped(&mut self, n: usize, context_base: usize) -> usize {
        let mut value: usize = 0;
        for idx in 0..n {
            let bit = self.get_bit(context_base + (1 << idx) + value);
            value |= bit << idx;
        }
        return value;
    }

    pub fn get_byte_with_reference(&mut self, ref_byte: u8, context_base: usize) -> usize {
        let mut mismatch_found = false;
        let mut value: usize = 0;
        for idx in 0..8 {
            let mut ctx_offset = 1 << idx;
            let mut ref_bit = 0;
            if !mismatch_found {
                ref_bit = if ((ref_byte << idx) & 0x80) == 0 { 0 } else { 1 };
                ctx_offset += if ref_bit == 0 { 0x100 } else { 0x200 };
            }
            let bit = self.get_bit(context_base + ctx_offset + value);
            value = (value << 1) + bit;
            mismatch_found |= bit != ref_bit;
        }
        return value;
    }

    pub fn get_raw_bit(&mut self) -> usize {
        self.renormalize();
        self.scale >>= 1;

        if self.value < self.scale {
            0
        } else {
            self.value -= self.scale;
            1
        }
    }
}

struct LZ77Output {
    expected_len: usize,
    mru: MRUList,
    decoded: Vec<u8>,
}

impl LZ77Output {
    pub fn new(output_len: usize) -> LZ77Output {
        LZ77Output {
            expected_len: output_len,
            mru: MRUList::new(),
            decoded: Vec::with_capacity(output_len),
        }
    }

    pub fn push(&mut self, byte: u8) {
        self.decoded.push(byte);
    }

    pub fn set_distance(&mut self, distance: usize) -> Result<(), DecodeError> {
        if distance > 0x7FFFFFFF || self.decoded.is_empty() {
            Err(DecodeError::NegativeDistance)
        } else {
            self.mru.push(distance);
            Ok(())
        }
    }

    pub fn recall_distance(&mut self, idx: usize) -> usize {
        self.mru.get_at(idx)
    }

    pub fn get_referenced_byte(&self) -> u8 {
        let distance = self.mru.get_recent();
        if distance >= self.decoded.len() {
            0
        } else {
            self.decoded[self.decoded.len() - 1 - distance]
        }
    }

    pub fn copy_referenced_bytes(&mut self, count: usize) {
        for _ in 0..count {
            let byte = self.get_referenced_byte();
            self.decoded.push(byte);
        }
    }

    pub fn get_byte_in_dword(&self) -> usize {
        self.decoded.len() & 3
    }

    pub fn finished(&self) -> Result<bool, DecodeError> {
        if self.decoded.len() > self.expected_len {
            Err(DecodeError::OutputTooBig)
        } else {
            Ok(self.decoded.len() == self.expected_len)
        }
    }

    pub fn is_empty(&self) -> bool {
        self.decoded.is_empty()
    }

    pub fn get_decoded(self) -> Vec<u8> {
        self.decoded
    }

    pub fn get_last_byte(&self) -> u8 {
        let len = self.decoded.len();
        if len == 0 {
            0
        } else {
            self.decoded[len - 1]
        }
    }
}

// State transitions:
//  0: "stable" state
//
//  1..6: intermediate states
//
//  7 -> 4 -> 1 -> 0
//  8 -> 5 -> 2 -> 0
//  9 -> 6 -> 3 -> 0
//
//  A -> 4 -> 1 -> 0
//  B -> 5 -> 2 -> 0

const STATE_TABLE: &[usize] = &[0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5];

pub fn decompress(input: &[u8]) -> Result<Vec<u8>, DecodeError> {
    let out_length = LittleEndian::read_u32(input) as usize;
    let mut arith = ArithDecoder::new(&input[5..]);
    let mut output = LZ77Output::new(out_length);

    let mut state = 0;
    while !output.finished()? {
        let refined_state = (state << 4) + output.get_byte_in_dword();
        if arith.get_bit(refined_state) == 0 {
            let last_byte = output.get_last_byte();
            let single_byte_context = 0x736 + ((last_byte as usize) >> 5) * 0x300;
            let next_byte;
            if state < 7 {
                next_byte = arith.get_n_bits(8, single_byte_context);
            } else {
                next_byte = arith.get_byte_with_reference(output.get_referenced_byte(), single_byte_context);
            }
            output.push(next_byte as u8);
            state = STATE_TABLE[state];
            continue;
        }

        let fetch_new_distance = arith.get_bit(state + 0xC0) == 0;

        let mut len_context;
        if fetch_new_distance {
            len_context = 0x332;
        } else {
            if output.is_empty() {
                return Err(DecodeError::ReferencingEmpty);
            }

            if arith.get_bit(state + 0xcc) == 0 {
                if arith.get_bit(refined_state + 0xF0) == 0 {
                    output.copy_referenced_bytes(1);
                    state = if state < 7 { 0x9 } else { 0xB };
                    continue;
                }
            } else {
                if arith.get_bit(state + 0xD8) == 0 {
                    output.recall_distance(1);
                } else {
                    if arith.get_bit(state + 0xE4) == 0 {
                        output.recall_distance(2);
                    } else {
                        output.recall_distance(3);
                    }
                }
            }
            state = if state < 7 { 0x8 } else { 0xb };
            len_context = 0x534;
        }

        let len_base;
        let len_bits;
        if arith.get_bit(len_context) == 0 {
            len_context += output.get_byte_in_dword() * 8 + 2;
            len_base = 0;
            len_bits = 3;
        } else {
            if arith.get_bit(len_context + 1) == 0 {
                len_context += output.get_byte_in_dword() * 8 + 0x82;
                len_base = 8;
                len_bits = 3;
            } else {
                len_context += 0x102;
                len_base = 0x10;
                len_bits = 8;
            }
        }

        let requested_copy_len = len_base + arith.get_n_bits(len_bits, len_context);
        if fetch_new_distance {
            let new_distance_code = arith.get_n_bits(6, (min(requested_copy_len, 3) << 6) + 0x1B0);
            let mut new_distance;
            if new_distance_code >= 4 {
                new_distance = (new_distance_code & 1) | 2;
                let additional_distance_bits = (new_distance_code >> 1) - 1;
                if additional_distance_bits < 6 {
                    new_distance = new_distance << additional_distance_bits;
                    new_distance |= arith.get_n_bits_flipped(additional_distance_bits, new_distance - new_distance_code + 0x2AF);
                } else {
                    for _ in 0..(additional_distance_bits - 4) {
                        new_distance = arith.get_raw_bit() + new_distance * 2;
                    }
                    new_distance = new_distance << 4;
                    new_distance |= arith.get_n_bits_flipped(4, 0x322);
                    if new_distance == 0xFFFFFFFF {
                        // requested_copy_len += 0x112;
                        break;
                    }
                }
            } else {
                new_distance = new_distance_code;
            }
            output.set_distance(new_distance)?;
            state = if state < 7 { 0x7 } else { 0xA };
        }
        output.copy_referenced_bytes(requested_copy_len + 2);
    }

    Ok(output.get_decoded())
}
