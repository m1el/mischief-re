use ::std::cmp::{min};
use ::byteorder::{ByteOrder, LittleEndian, BigEndian};

#[derive(Debug)]
pub enum DecodeError {
    ReferencingEmpty = 1,
    NegativeDistance = 3,
    OutputTooBig = 4,
}

const MRU_SIZE: usize = 4;

/// Stores the most recently used values for some quantity,
/// and allows recalling recently used values by index.
struct MRUList {
    history: [usize; MRU_SIZE],
}

impl MRUList {
    pub fn new(size: usize) -> MRUList {
        MRUList {
            history: [0; MRU_SIZE],
        }
    }

    pub fn mru(&self) -> usize {
        self.history[0]
    }

    pub fn add_value(&mut self, value: usize) {
        for i in (1..MRU_SIZE).rev() {
            self.history[i] = self.history[i - 1]
        }
        self.history[0] = value;
    }

    pub fn pick_recently_used(&mut self, index: usize) -> usize {
        let val = self.history[index];
        for i in (1..index).rev() {
            self.history[i] = self.history[i - 1]
        }
        self.history[0] = val;
        val
    }
}

/// Decoder for data that is encoded using binary arithmetic coding.
/// This implementation uses an integer threshold in the range 1..0x7ff,
/// with 0x400 being used as (quite close to) neutral value.
/// A function get_raw_bit, that decodes 0 and 1 with equal probability
/// and incurs less rounding errors than get_bit with a threshold of 0x400
/// is also provided.
struct BinaryArithmeticDecoder<'a> {
    scale: u32,
    value: u32,
    input: &'a[u8],
}

impl<'a> BinaryArithmeticDecoder<'a> {
    pub fn new(input: &'a[u8]) -> BinaryArithmeticDecoder<'a> {
        let value = BigEndian::read_u32(input);
        BinaryArithmeticDecoder {
            scale: 0xFFFFFFFF,
            value: value,
            input: &input[4..],
        }
    }

    /// Given threshold, decodes a bit and updates threshold
    pub fn get_bit(&mut self, threshold: &mut u16) -> bool {
        self.renormalize();
        let scaled_threshold = ((self.scale >> 0x0b) * (*threshold as u32));

        if self.value < scaled_threshold {
            self.scale = scaled_threshold;
            *threshold = (*threshold - (*threshold >> 5));
            return false;
        } else {
            self.value -= scaled_threshold;
            self.scale -= scaled_threshold;
            *threshold = (*threshold - ((*threshold+0x1f) >> 5)) + 1*0x40;
            return true;
        }
    }

    pub fn get_raw_bit(&mut self) -> bool {
        self.renormalize();
        self.scale >>= 1;
        if self.value < self.scale {
            return false;
        } else {
            self.value -= self.scale;
            return true;
        }
    }

    fn next_byte(&mut self) -> u32 {
        let (byte, rest) = self.input.split_first().unwrap();
        self.input = rest;
        *byte as u32
    }

    fn renormalize(&mut self) {
        if self.scale < 0x01000000 {
            self.scale = self.scale.wrapping_shl(8);
            self.value = self.value.wrapping_shl(8) | self.next_byte();
        }
    }
}

const MAX_UNARY_SIZE: usize = 4;
/// Reads a numbers from an BinaryArithmeticDecoder that are binarized
/// using unary encoding. A different context is used for each bit of
/// the number.
/// The result of get_value is the number of "one" bits encountered
/// before either a "zero" bit has been read or maxval bits have been
/// consumed.
struct UnaryGetter {
    size: usize,
    thresholds: [u16; MAX_UNARY_SIZE],
}

impl UnaryGetter {
    pub fn new(size: usize) -> UnaryGetter {
        assert!(size <= MAX_UNARY_SIZE);
        UnaryGetter {
            size: size,
            thresholds: [0; MAX_UNARY_SIZE],
        }
    }

    pub fn get_value(&mut self, decoder: &mut BinaryArithmeticDecoder) -> usize {
        let mut result = 0;
        for i in 0..self.size {
            if decoder.get_bit(&mut self.thresholds[i]) {
                return result;
            }
            result += 1;
        }
        return result;
    }
}

pub fn decompress(input: &[u8]) -> Result<Vec<u8>, DecodeError> {
    Ok(Vec::new())
}

/*

class MSBFirstGetter():
    '''
    Reads a numbers from an BinaryArithmeticDecoder that are binarized
    using MSB first binary representation. The context used when reading
    a bit depends on all the earlier bits read for this number. So
    the MSB is always obtained using the same context, while the second-most
    significant bit is obtained using different contexts whether the MSB
    is one or zero. The third-most significant bit is decoded using one
    out of four contexts and so on.
    '''
    def __init__(self, decoder, bitcount):
        self.layers = [[AdaptiveBitGetter(decoder) for _ in range(1<<layer)]
                       for layer in range(bitcount)]

    def get_value(self):
        value = 0
        for layer in self.layers:
            value = (value << 1) + layer[value].get_bit()
        return value

class LSBFirstGetter():
    '''
    Reads a numbers from an BinaryArithmeticDecoder that are binarized
    using LSB first binary representation. The context used when reading
    a bit depends on all the earlier bits read for this number. So
    the LSB is always obtained using the same context, while the second-least
    significant bit is obtained using different contexts whether the LSB
    is one or zero. The third-least significant bit is decoded using one
    out of four contexts and so on.
    '''
    def __init__(self, decoder, bitcount):
        self.layers = [[AdaptiveBitGetter(decoder) for _ in range(1<<layer)]
                       for layer in range(bitcount)]

    def get_value(self):
        value = 0
        bitnum = 0
        for layer in self.layers:
            value |= layer[value].get_bit() << bitnum
            bitnum += 1
        return value

class LZ77Output():
    '''
    Generic LZ77 output handling.
    This class manages an output buffer, and is able to append single bytes
    or copy from earlier parts of the buffer, given a distance to the end.
    A distance of 0 means the last byte already stored.
    '''
    def __init__(self):
        self.decoded = bytearray()

    # LZ77 literal code
    def literal_byte(self, byte):
        self.decoded.append(byte)

    # LZ77 distance use/copying
    def copy_bytes(self, distance, count):
        for _ in range(count):
            self.decoded.append(self.get_earlier_byte(distance))

    # buffer inspection
    def get_earlier_byte(self, distance):
        if distance >= len(self.decoded):
            return 0
        else:
            return self.decoded[-distance-1]

    def get_byte_in_dword(self):
        return len(self.decoded) & 3

    def get_data(self):
        return self.decoded

    def get_length(self):
        return len(self.decoded)

class LiteralGetter():
    '''
    Contains the algorithm to obtain the value of a literal byte
    for the mischief decompressor.
    Obtaining a literal byte can optionally make use of a context byte.
    If the previous LZ77 was a copy operation, the first byte not copied
    is used as context byte (with the expectation that the byte to decode
    is similar).
    If a context byte is given, bits are decoded using different contexts
    whether the context byte has a one or a zero at that position. As soon
    as a mismatch between the context byte and the newly decoded byte is
    detected (or if no context byte is given), decoding switches to a third
    set of contexts (and behaves like the MSBFirstGetter).
    '''
    def __init__(self, decoder):
        self.no_context_layers =   [[AdaptiveBitGetter(decoder) for _ in range(1<<layer)]
                                    for layer in range(8)]
        self.context_zero_layers = [[AdaptiveBitGetter(decoder) for _ in range(1<<layer)]
                                    for layer in range(8)]
        self.context_one_layers =  [[AdaptiveBitGetter(decoder) for _ in range(1<<layer)]
                                     for layer in range(8)]

    def get_value(self, context_byte):
        use_context = context_byte != None
        value = 0
        for bitnr in range(8):
            if use_context:
                refbit = ((context_byte << bitnr) & 0x80) != 0
                if refbit == 0:
                    layers = self.context_zero_layers
                else:
                    layers = self.context_one_layers
            else:
                layers = self.no_context_layers
            bit = layers[bitnr][value].get_bit()
            value = value * 2 + bit
            if use_context and bit != refbit:
                use_context = False
        return value

class LengthGetter():
    '''
    Contains the algorithm to obtain the value of the copy length
    for the mischief decompressor.
    The length is first classified into one of three ranges (0..7,
    8..15, 16..271). The position in each range is stored as MSB-first
    binarized number. For the position in the two short ranges, four
    subcontexts exist. The number of th subcontext has to be supplied
    by the caller and is chosen depending on the current LZ77 output
    position relative to 32-bit-boundaries in the mischief format.
    '''
    def __init__(self, decoder):
        self.range_getter = UnaryGetter(decoder, 2)
        shared_long_length_getter = MSBFirstGetter(decoder, 8)
        # tuples of "base, getter for offset"
        self.ranges = [[(0, MSBFirstGetter(decoder, 3)),
                        (8, MSBFirstGetter(decoder, 3)),
                        (16,shared_long_length_getter)] for _ in range(4)]

    def get_value(self, subcontext):
        (base, offset_getter) = self.ranges[subcontext][self.range_getter.get_value()]
        return base + offset_getter.get_value()

class DistanceGetter():
    '''
    Contains the algorithm to obtain the value of the copy distance
    for the mischief decompressor.
    The distance is first classified into coarse ranges: The distances
    0 to 3 are directly encoded at this step, while bigger distances
    of up to 2^32 are divided in 60 ranges, depending on the position
    of the MSB (31..2) and the value of the second-most significant bit.
    For distances above 128, some of the bits are stored "raw" without
    an adaptive context model. The low-order bits for each range are
    modelled using a different context.
    '''
    def __init__(self, decoder):
        self.decoder = decoder
        self.coarse_distance_getter = [MSBFirstGetter(decoder, 6) for _ in range(4)]
        self.medium_distance_getters = \
            [[LSBFirstGetter(decoder, n) for _ in range(2)]
                for n in range(1, 6)]
        self.long_distance_low_bits_getter = LSBFirstGetter(decoder, 4)

    def get_value(self, length_code):
        coarse_distance = self.coarse_distance_getter[min(length_code, 3)].get_value()
        if coarse_distance < 4:
            return coarse_distance
        else:
            next_to_MSB = coarse_distance & 1
            extra_bits_to_fetch = 1 + ((coarse_distance - 4) >> 1)
            result_high = (2 | next_to_MSB) << extra_bits_to_fetch
            if extra_bits_to_fetch < 6:
                return result_high | self.medium_distance_getters[extra_bits_to_fetch-1][next_to_MSB].get_value()
            else:
                for bitnum in range(extra_bits_to_fetch - 1, 3, -1):
                    result_high |= self.decoder.get_raw_bit() << bitnum
                return result_high | self.long_distance_low_bits_getter.get_value()

class State():
    '''
    State of the mischief decompressor.
    The state consists of a set of models for LZ77 control information,
    namely the decision whether the next LZ77 symbol is a reference or a
    literal, the kind of distance encoding for a reference (MRU index vs. 
    explicitly coded) and the decision whether a reference with the most
    recently used distance is a "quick one-byte copy" or a longer area.
    Furthermore, the state is linked to a (possibly) different state the
    decoder should switch to after decoding a literal code in this state.
    The next state after reference codes are hard-coded in the main
    decoder procedure.
    '''
    def __init__(self, decoder, state_after_literal = None):
        self.after_literal = state_after_literal or self
        self.is_reference_code = [AdaptiveBitGetter(decoder) for _ in range(4)]
        self.get_reference_kind = UnaryGetter(decoder, 4)
        self.get_kind_1_nontrivial = [AdaptiveBitGetter(decoder) for _ in range(4)]
        

def mischief_unpack(byte_input):
    '''
    this function unpacks bytes and returns an unpacked byte array
    '''
    (out_length,) = struct.unpack('I', byte_input[0:4])
    decoder = BinaryArithmeticDecoder(byte_input[5:])
    output = LZ77Output()

    # literal_getters is indexed by the top 3 bits of the previous byte
    literal_getters = [LiteralGetter(decoder) for _ in range(8)]
    new_distance_length_getter = LengthGetter(decoder)
    reused_distance_length_getter = LengthGetter(decoder)
    distance_getter = DistanceGetter(decoder)

    distance_history = MRUList(4)

    base_state = State(decoder)
    intermediate_after_new_distance = State(decoder, State(decoder, base_state))
    intermediate_after_reused_distance = State(decoder, State(decoder, base_state))
    intermediate_after_trivial_copy = State(decoder, State(decoder, base_state))
    states_after_new_distance = [State(decoder, intermediate_after_new_distance),
                                 State(decoder, intermediate_after_new_distance)]
    common_after_reuse_or_trivial_after_ref = \
        State(decoder, intermediate_after_reused_distance)
    states_after_reused_distance = [State(decoder, intermediate_after_reused_distance),
                                    common_after_reuse_or_trivial_after_ref]
    states_after_trivial_copy = [State(decoder, intermediate_after_trivial_copy),
                                 common_after_reuse_or_trivial_after_ref]

    last_was_reference = False
    copy_mismatch_byte = None
    state = base_state

    while output.get_length() < out_length:
        if state.is_reference_code[output.get_byte_in_dword()].get_bit() == 0:
            # LZ77 literal: add a single (new) byte to the output
            literal_getter = literal_getters[output.get_earlier_byte(0) >> 5]
            output.literal_byte(literal_getter.get_value(copy_mismatch_byte))
            state = state.after_literal
            copy_mismatch_byte = None
            last_was_reference = False
        else:
            # LZ77 reference: copy a part of previous output
            reference_kind = state.get_reference_kind.get_value()
            if reference_kind == 0:
                copy_len = new_distance_length_getter.get_value(output.get_byte_in_dword()) + 2
                distance = distance_getter.get_value(copy_len - 2)
                distance_history.add_value(distance)
                state = states_after_new_distance[last_was_reference]
            elif reference_kind == 1 and \
                 not state.get_kind_1_nontrivial[output.get_byte_in_dword()].get_bit():
                copy_len = 1
                distance = distance_history.mru()
                state = states_after_trivial_copy[last_was_reference]
            else:
                copy_len = reused_distance_length_getter.get_value(output.get_byte_in_dword()) + 2
                distance = distance_history.pick_recently_used(reference_kind - 1)
                state = states_after_reused_distance[last_was_reference]
            if output.get_length() + copy_len > out_length:
                raise Exception("Unpacking generates excess data")
            output.copy_bytes(distance, copy_len)
            copy_mismatch_byte = output.get_earlier_byte(distance) # first non-copied byte
            last_was_reference = True

    return output.get_data()
*/
