import struct
import sys

# byte table, probably for state machine
next_state = [
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
        0x05, 0x06, 0x04, 0x05, 0x07, 0x07, 0x07, 0x07,
        0x07, 0x07, 0x07, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A]

MAXINT = 0xFFFFFFFF

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

class ArithDecoder():
    def __init__(self, byte_input):
        self.scale = 0xFFFFFFFF
        (self.value,) = struct.unpack('>I', byte_input[0:4])
        self.input = iter(byte_input[4:] + bytearray([0,0,0,0]))
        self.thresholds = [0x0400] * 0x1F38
    def renormalize(self):
        if self.scale < 0x01000000:
            self.scale = ((self.scale << 8) & MAXINT)
            self.value = ((self.value << 8) & MAXINT) | self.input.next()
    def get_bit(self, contextidx):
        self.renormalize()
        threshold = self.thresholds[contextidx]
        scaled_threshold = ((self.scale >> 0x0b) * threshold) & MAXINT
        if self.value < scaled_threshold:
            self.thresholds[contextidx] = (threshold - ((threshold+0x1f) >> 5)) + 1*0x40
            self.scale = scaled_threshold
            return 0
        else:
            self.thresholds[contextidx] = (threshold - ( threshold       >> 5)) + 0*0x40
            self.value -= scaled_threshold
            self.scale -= scaled_threshold
            return 1
    def get_n_bits(self, n, contextbase):
        value = 0
        for bitnum in range(n):
            bit = self.get_bit(contextbase + (1 << bitnum) + value)
            value = (value << 1) + bit
        return value
    def get_n_bits_flipped(self, n, contextbase):
        value = 0
        flipped_value = 0
        for bitnum in range(n):
            bit = self.get_bit(contextbase + (1 << bitnum) + value)
            value = (value << 1) + bit
            flipped_value |= (bit << bitnum)
        return flipped_value
    def get_byte_with_reference(self, refbyte, contextbase):
        mismatch_found = False
        value = 0
        # 00468127
        for bitnr in range(8):
            ctxoffset = (1 << bitnr)
            if mismatch_found:
                ctxoffset += 0
            else:
                refbit = ((refbyte << bitnr) & 0x80) != 0
                if refbit == 0:
                    ctxoffset += 0x100
                else:
                    ctxoffset += 0x200
            bit = self.get_bit(contextbase + ctxoffset + value)
            value = value * 2 + bit
            if bit != refbit:
                mismatch_found = True
        return value

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
        self.distance_history = MRUList()
        self.decoded = bytearray()

    def get_referenced_byte(self):
        distance = self.distance_history.mru()
        if distance > len(self.decoded):
            return 0
        else:
            return self.decoded[-distance-1]

    def copy_referenced_byte(self):
        self.decoded.append(self.get_referenced_byte())

def mischief_unpack(byte_input):
    '''
    this function unpacks bytes and returns an unpacked byte array
    '''
    (out_length,) = struct.unpack('I', byte_input[0:4])
    arith = ArithDecoder(byte_input[5:])
    output = LZ77Output()
    state_nr = 0

    # 00467FE1
    while len(output.decoded) < out_length:
        bytenr_in_dword = len(output.decoded) & 3
        refined_state_nr = (state_nr << 4) + bytenr_in_dword
        # 0046801D
        if arith.get_bit(refined_state_nr) == 0:
            prev_byte = 0 if len(output.decoded) == 0 else output.decoded[-1]
            single_byte_context = 0x736 + (prev_byte >> 5) * 0x300
            if state_nr < 7:
                next_byte = arith.get_n_bits(8, single_byte_context)
            # 004680FB
            else:
                next_byte = arith.get_byte_with_reference(output.get_referenced_byte(), single_byte_context)
            output.decoded.append(next_byte)
            state_nr = next_state[state_nr]
            continue
        # 0046821C
        fetch_new_distance = arith.get_bit(state_nr + 0xC0) == 0
        if fetch_new_distance:
            len_context = 0x332
        # 00468241
        else:
            # 00468260
            if len(output.decoded) == 0:
                raise Exception("Error 1")
            # 00468294
            if arith.get_bit(state_nr + 0xCC) == 0:
                # 004682E3
                if arith.get_bit(refined_state_nr + 0xF0) == 0:
                    # 00468309
                    output.copy_referenced_byte()
                    # 00468322
                    state_nr = 0x9 if state_nr < 7 else 0xB
                    continue
            # 00468348
            else:
                # 00468389
                if arith.get_bit(state_nr+0xD8) == 0:
                    output.distance_history.pick_recently_used(1)
                # 004683A5
                else:
                    # 004683E1
                    if arith.get_bit(state_nr+0xE4) == 0:
                        output.distance_history.pick_recently_used(2)
                    # 00468402
                    else:
                        output.distance_history.pick_recently_used(3)
            # 00468437
            state_nr = 8 if state_nr < 7 else 0xb
            len_context = 0x534
        # 0046846B
        if arith.get_bit(len_context) == 0:
            len_context += bytenr_in_dword * 8 + 2
            len_base = 0
            len_bits = 3
        # 00468497
        else:
            # 004684CF
            if arith.get_bit(len_context + 1) == 0:
                len_context += bytenr_in_dword * 8 + 0x82
                len_base = 8
                len_bits = 3
            # 004684F9
            else:
                len_context += 0x102
                len_base = 0x10
                len_bits = 8
        requested_copy_len = len_base + arith.get_n_bits(len_bits, len_context)
        # 0046858A
        if fetch_new_distance:
            # 004685AE-00468794 (unwound loop)
            new_distance_code = arith.get_n_bits(6, (min(requested_copy_len,3) << 6) + 0x1B0)
            # 00468794
            if new_distance_code >= 4:
                new_distance = (new_distance_code & 1) | 2
                additional_distance_bits = (new_distance_code >> 1) - 1
                # 004687B3
                if new_distance_code < 0x0e:
                    new_distance = new_distance << additional_distance_bits
                    # 004687CE
                    new_distance |= arith.get_n_bits_flipped(additional_distance_bits, new_distance - new_distance_code + 0x2AF)
                # 00468831
                else:
                    # 00468846
                    for _ in range(additional_distance_bits - 4):
                        new_distance = arith.get_raw_bit() + (new_distance * 2)
                    # 0046886D-004689F6 (unwound loop)
                    new_distance = new_distance << 4
                    new_distance |= arith.get_n_bits_flipped(4, 0x322)
                    # 004689F6
                    if new_distance == -1:
                        requested_copy_len += 0x112
                        break
            else:
                new_distance = new_distance_code
            # 004689FC
            output.distance_history.add_value(new_distance)
            # 00468A2B
            if (new_distance < 0) or (len(output.decoded) == 0):
                raise Exception("Error 3")
            # 00468A31
            state_nr = 0x7 if state_nr < 0x7 else 0xa

        requested_copy_len += 2
        # 00468A51
        if out_length == len(output.decoded):
            raise Exception("Error 4")
        # 00468A5B
        copy_count = min(out_length - len(output.decoded), requested_copy_len)
        # 00468A8C
        for _ in xrange(copy_count):
            output.copy_referenced_byte()
    return output.decoded


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
