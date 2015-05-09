import struct
import sys

class MRUList():
    def __init__(self):
        self.history = [0,0,0,0]

    def mru(self):
        return self.history[0]

    def add_value(self, new_val):
        self.history[1:4] = self.history[0:3]
        self.history[0] = new_val

    def pick_recently_used(self, index):
        (self.history[0], self.history[1:index+1]) = \
            (self.history[index], self.history[0:index])
        return self.history[0]

class BitGetter():
    def __init__(self, decoder):
        self.decoder = decoder
        self.threshold = 0x400

    def get_bit(self):
        bit = self.decoder.get_bit_(self.threshold)
        if bit == 0:
            self.threshold = (self.threshold - ((self.threshold+0x1f) >> 5)) + 1*0x40
        else:
            self.threshold = (self.threshold - ( self.threshold       >> 5)) + 0*0x40
        return bit

class UnaryGetter():
    def __init__(self, decoder, maxval):
        self.getters = [BitGetter(decoder) for _ in range(maxval)]

    def get_value(self):
        result = 0
        for getter in self.getters:
            if getter.get_bit() == 0:
                return result
            result = result + 1
        return result

class MSBFirstGetter():
    def __init__(self, decoder, bitcount):
        self.layers = [[BitGetter(decoder) for _ in range(1<<layer)] for layer in range(bitcount)]

    def get_value(self):
        value = 0
        for layer in self.layers:
            value = (value << 1) + layer[value].get_bit()
        return value

class LSBFirstGetter():
    def __init__(self, decoder, bitcount):
        self.layers = [[BitGetter(decoder) for _ in range(1<<layer)] for layer in range(bitcount)]

    def get_value(self):
        value = 0
        bitnum = 0
        for layer in self.layers:
            value |= layer[value].get_bit() << bitnum
            bitnum += 1
        return value

class ByteWithContextGetter():
    def __init__(self, decoder):
        self.layers = [[[BitGetter(decoder) for _ in range(1<<layer)] for _ in range(3)] for layer in range(8)]

    def get_value(self, context_byte):
        use_context = context_byte != None
        value = 0
        for bitnr in range(8):
            if use_context:
                refbit = ((context_byte << bitnr) & 0x80) != 0
                if refbit == 0:
                    way = 1
                else:
                    way = 2
            else:
                way = 0
            bit = self.layers[bitnr][way][value].get_bit()
            value = value * 2 + bit
            if use_context and bit != refbit:
                use_context = False
        return value

class ArithDecoder():
    def __init__(self, byte_input):
        self.scale = 0xFFFFFFFF
        (self.value,) = struct.unpack('>I', byte_input[0:4])
        self.input = iter(byte_input[4:] + bytearray([0,0,0,0]))
    def renormalize(self):
        if self.scale < 0x01000000:
            self.scale <<= 8
            self.value = (self.value << 8) | next(self.input)
    def get_bit_(self, threshold):
        self.renormalize()
        scaled_threshold = ((self.scale >> 0x0b) * threshold)
        if self.value < scaled_threshold:
            self.scale = scaled_threshold
            return 0
        else:
            self.value -= scaled_threshold
            self.scale -= scaled_threshold
            return 1

    def get_raw_bit(self):
        self.renormalize()
        self.scale >>= 1
        if self.value < self.scale:
            return 0
        else:
            self.value -= self.scale
            return 1

class LZ77Output():
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
        if len(self.decoded) > expected_length:
            raise Exception("Unpacking generated excess data")

class LengthGetter():
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
    def __init__(self, decoder, state_after_literal = None):
        self.after_literal = state_after_literal or self
        self.is_reference_code = [BitGetter(decoder) for _ in range(4)]
        self.get_reference_kind = UnaryGetter(decoder, 4)
        self.get_kind_1_nontrivial = [BitGetter(decoder) for _ in range(4)]
        

def mischief_unpack(byte_input):
    '''
    this function unpacks bytes and returns an unpacked byte array
    '''
    (out_length,) = struct.unpack('I', byte_input[0:4])
    decoder = ArithDecoder(byte_input[5:])
    output = LZ77Output()

    # literal_getters is indexed by the top 3 bits of the previous byte
    literal_getters = [ByteWithContextGetter(decoder) for _ in range(8)]
    new_distance_length_getter = LengthGetter(decoder)
    reused_distance_length_getter = LengthGetter(decoder)
    distance_getter = DistanceGetter(decoder)

    distance_history = MRUList()

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


ART_MAGICS = set([b'\xc5\xb3\x8b\xe9', b'\xc5\xb3\x8b\xe7'])

def read_byte(data, pos):
    return (data[pos], pos+1)


def read_int(data, pos):
    (val,) = struct.unpack('I', data[pos:pos+4])
    return (val, pos+4)


def read_int_array(data, pos, count):
    val = list(struct.unpack('%dI'%count,
                             data[pos:pos+4*count]))
    return (val, pos+4*count)


def read_float(data, pos):
    (val,) = struct.unpack('f', data[pos:pos+4])
    return (val, pos+4)


def read_float_array(data, pos, n):
    floats = list(struct.unpack('%df'%n,
                                data[pos:pos+4*n]))
    return (floats, pos+4*n)


def read_float_matrix(data, pos, n, m):
    floats = list(struct.unpack('%df'%(n*m),
                                data[pos:pos+4*n*m]))
    return ([floats[i*n:i*n+n] for i in range(0,m)],
            pos+4*n*m)


def read_bytes(data, pos, length):
    return (data[pos:pos+length], pos+length)


def read_string(data, pos, length):
    val = data[pos:pos+length]
    return (val.split(b'\x00', 1)[0].decode('utf-8'),
            pos+length)


def read_color(data, pos):
    val = (data[pos], data[pos+1], data[pos+2])
    return (val, pos+3)


def read_pen_info(data, pos):
    val = {}
    (val['type'], pos) = read_int(data, pos)
    (val['color'], pos) = read_color(data, pos)
    (val['noise'], pos) = read_float(data, pos)
    (val['size'], pos) = read_float(data, pos)
    (val['size_min'], pos) = read_float(data, pos)
    (val['opacity'], pos) = read_float(data, pos)
    (val['opacity_min'], pos) = read_float(data, pos)
    (val['is_eraser'], pos) = read_int(data, pos)
    return (val, pos)


def read_layer_info(data, pos):
    val = {}
    (val['visible'], pos) = read_int(data, pos)
    (val['opacity'], pos) = read_float(data, pos)
    (val['name'], pos) = read_string(data, pos, 256)
    (val['action_count'], pos) = read_int(data, pos)
    (val['matrix'], pos) = read_float_matrix(data, pos, 4, 4)
    (val['zoom'], pos) = read_float(data, pos)
    return (val, pos)


def read_image(data, pos):
    val = {}
    (val['type'], pos) = read_int(data, pos)
    (size, pos) = read_int(data, pos)
    (val['raw'], pos) = read_bytes(data, pos, size)
    return (val, pos)


def read_action(data, pos):
    val = {}
    (val['layer'], pos) = read_int(data, pos)
    (val['action_id'], pos) = read_int(data, pos)

    if val['action_id'] == 0x01:
        val['action_name'] = 'stroke'
        (point_count, pos) = read_int(data, pos)
        points = []
        point = {}
        (point['x'], pos) = read_float(data, pos)
        (point['y'], pos) = read_float(data, pos)
        (point['p'], pos) = read_float(data, pos)
        points.append(point)

        x = point['x']
        y = point['y']

        for i in range(point_count - 1):
            (tmp, pos) = read_int(data, pos)
            (byt, pos) = read_byte(data, pos)
            dx = tmp & 0x3fff
            if tmp & (1<<14): dx = -dx
            dy = (tmp >> 15) & 0x3fff
            if tmp & (tmp << 29): dy = -dy
            p = (tmp >> 30) | (byt << 2)
            x += dx/32.
            y += dy/32.
            points.append({'x': x, 'y': y, 'p': p/0x3ff})

        val['points'] = points

    elif val['action_id'] == 0x08:
        val['action_name'] = 'unknown_08'
        (val['argument'], pos) = read_int(data, pos)

    elif val['action_id'] == 0x33:
        val['action_name'] = 'pen_matrix'
        (val['matrix'], pos) = read_float_matrix(data, pos, 4, 4)
        (val['zoom'], pos) = read_float(data, pos)

    elif val['action_id'] == 0x34:
        val['action_name'] = 'pen_properties'
        (val['type'], pos) = read_int(data, pos)
        (val['noise'], pos) = read_float(data, pos)
        (val['size'], pos) = read_float(data, pos)
        (val['size_min'], pos) = read_float(data, pos)
        (val['opacity'], pos) = read_float(data, pos)
        (val['opacity_min'], pos) = read_float(data, pos)

    elif val['action_id'] == 0x35:
        val['action_name'] = 'pen_color'
        (val['color'], pos) = read_color(data, pos)

    elif val['action_id'] == 0x36:
        val['action_name'] = 'is_eraser'
        (val['is_eraser'], pos) = read_int(data, pos)

    elif val['action_id'] == 0x0f:
        val['action_name'] = 'paste_layer'
        (val['from_layer'], pos) = read_int(data, pos)
        (val['rect'], pos) = read_float_array(data, pos, 4)
        (val['matrix_1'], pos) = read_float_matrix(data, pos, 4, 4)
        (val['zoom_1'], pos) = read_float(data, pos)
        (val['matrix_2'], pos) = read_float_matrix(data, pos, 4, 4)
        (val['zoom_2'], pos) = read_float(data, pos)

    elif val['action_id'] == 0x0d:
        val['action_name'] = 'layer_matrix'
        (val['matrix'], pos) = read_float_matrix(data, pos, 4, 4)
        (val['zoom'], pos) = read_float(data, pos)

    elif val['action_id'] == 0x0e:
        val['action_name'] = 'cut'
        (val['rect'], pos) = read_float_array(data, pos, 4)

    elif val['action_id'] == 0x0c:
        val['action_name'] = 'merge_layer'
        (val['from_layer'], pos) = read_int(data, pos)
        (val['opacity_src'], pos) = read_float(data, pos)
        (val['opactty_dst'], pos) = read_float(data, pos)
        (val['matrix'], pos) = read_float_matrix(data, pos, 4, 4)
        (val['zoom'], pos) = read_float(data, pos)

    elif val['action_id'] == 0x07:
        val['action_name'] = 'draw_image'
        (val['dst_center'], pos) = read_float_array(data, pos, 2)
        (val['dst_size'], pos) = read_float_array(data, pos, 2)
        (val['unknown'], pos) = read_int(data, pos)
        (val['src_size'], pos) = read_int_array(data, pos, 2)
        (val['image_id'], pos) = read_int(data, pos)

    else:
        import binascii
        print('unknown action: %x' % val['action_id'])
        print(binascii.hexlify(data[pos:pos+200]))
        die()

    return (val, pos)


class ArtParser(object):
    '''
    Class for parsing an .art file.
    Usage: parsed = ArtParser(filename)
    '''
    data = None
    raw_size = 0
    version = None
    active_layer_num = None
    unknown_08 = None
    background_color = None
    background_alpha = None
    unknown_13 = None
    unknown_17 = None
    unknown_1b = None
    unknown_1f = None
    pen_info = None
    unknown_42 = None
    unknonw_46 = None
    view_matrix = None
    view_zoom = None
    layer_order = None
    layers = None
    images = None
    actions = None
    unknown_eof = None

    def __init__(self, fname):
        with open(fname, 'rb') as fd:
            header = fd.read(0x28)
            if len(header) < 0x28:
                raise Exception('file is too small to be an .art file')
            if header[0:4] not in ART_MAGICS:
                raise Exception('bad file magic')

            (self.raw_size,) = struct.unpack('I', header[0x24:0x28])
            self.data = fd.read(self.raw_size)
            self.data = mischief_unpack(self.data)
            self.parse_unpacked()


    def parse_unpacked(self):
        pos = 0
        data = self.data
        (self.version, pos) = read_int(data, pos)
        (self.active_layer_num, pos) = read_int(data, pos)
        (self.unknonw_08, pos) = read_int(data, pos)
        (self.background_color, pos) = read_color(data, pos)
        (self.background_alpha, pos) = read_float(data, pos)
        (self.unknown_13, pos) = read_int(data, pos)
        (self.unknown_17, pos) = read_int(data, pos)
        (self.unknown_1b, pos) = read_int(data, pos)
        (self.unknown_1f, pos) = read_int(data, pos)
        (self.pen_info, pos) = read_pen_info(data, pos)
        (self.unknown_42, pos) = read_int(data, pos)
        (self.unknown_46, pos) = read_float(data, pos)
        (self.view_matrix, pos) = read_float_matrix(data, pos, 4, 4)
        (self.view_zoom, pos) = read_float(data, pos)
        (order_count, pos) = read_int(data, pos)
        (self.layer_order, pos) = read_int_array(data, pos, order_count)

        (layer_count, pos) = read_int(data, pos)
        self.layers = []

        for i in range(layer_count):
            (layer_info, pos) = read_layer_info(data, pos)
            self.layers.append(layer_info)

        (images_count, pos) = read_int(data, pos)
        self.images = []

        for i in range(images_count):
            (image, pos) = read_image(data,pos)
            self.images.append(image)

        (action_count, pos) = read_int(data, pos)
        self.actions = []

        for i in range(action_count):
            (action, pos) = read_action(data, pos)
            self.actions.append(action)

        (self.unknown_eof, pos) = read_int(data, pos)


# simple wrapper for calling this file from command line
def main(argv):
    from pprint import pprint
    if len(argv) < 2:
        print('usage: artparser.py <input file>')
        return 1

    art = ArtParser(argv[1])
    # output = getattr(sys.stdout, 'buffer', sys.stdout)
    # output.write(art.data)
    print('pen info:')
    pprint(art.pen_info)
    print('view matrix:')
    pprint(art.view_matrix)
    print('layer order:')
    pprint(art.layer_order)
    print('layer info:')
    pprint(art.layers)
    # print('images:')
    # pprint(art.images)
    print('actions:')
    pprint(art.actions)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
