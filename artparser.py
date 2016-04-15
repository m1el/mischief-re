import struct
import sys

# byte table, probably for state machine
TABLE_50B8D8 = [
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
        0x05, 0x06, 0x04, 0x05, 0x07, 0x07, 0x07, 0x07,
        0x07, 0x07, 0x07, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x01, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
        0x03, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00,
        0x05, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00,
        0x04, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00,
        0x07, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
        0x07, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
        0x07, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
        0x07, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00,
        0x0A, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00,
        0x0A, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00,
        0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
        0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
        0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
        0x08, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00,
        0x0B, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00,
        0x0B, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00,
        0x09, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00,
        0x09, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00,
        0x09, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00,
        0x09, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00,
        0x0B, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00,
        0x0B, 0x00, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00]

MAXINT = 0xFFFFFFFF

class UnpackerState():
    def __init__(self):
        self.EAX = 0
        self.ESI = 0 # ESI
        self.in_pos = 0 # sp_10
        self.sp_14 = 0
        self.sp_18 = 0
        self.out_pos = 0 # sp_1c
        self.sp_20 = 0
        self.sp_24 = 0
        self.sp_2c = 0
        self.sp_28 = 0
        self.sp_30 = 0
        # self.garbage_p = 0 # sp_3c
        self.sp_38 = 0
        self.sp_40 = 0
        self.sp_44 = 0
        self.sp_4c = 0
        self.sp_64 = 0
    def __str__(self):
        attrs = ['EAX', 'ESI', 'out_pos', 'in_pos']
        return '\n'.join(['{0}: {1}'.format(i, hex(getattr(self, i)))
            for i in attrs])


def _pop_byte(state, byte_input):
    if state.EAX < 0x01000000:
        state.EAX = ((state.EAX << 8) & MAXINT)
        state.ESI = ((state.ESI << 8) & MAXINT) | byte_input[state.in_pos]
        state.in_pos = state.in_pos + 1


def mischief_unpack(byte_input):
    '''
    this function unpacks bytes and returns an unpacked byte array
    '''
    state = UnpackerState()
    state.EAX = 0xFFFFFFFF
    (unpacked_size,) = struct.unpack('I', byte_input[0:4])
    (state.ESI,) = struct.unpack('>I', byte_input[5:9])
    state.in_pos = 9
    packed_length = len(byte_input)
    byte_input += bytearray([0,0,0,0])
    decoded_length = unpacked_size
    state.sp_20 = 1
    state.sp_28 = 1
    state.sp_2c = 1
    state.sp_40 = 1
    state.sp_64 = decoded_length
    state.sp_38 = decoded_length
    sp_50 = 0

    decoded = bytearray(decoded_length)
    garbage_length = 0x3E70
    garbage = [0x0400] * (garbage_length // 2)

    # 00467FE1
    while state.in_pos < packed_length and state.out_pos < decoded_length:
        _pop_byte(state, byte_input)
        edi = state.sp_18
        ebp = 0 # state.garbage_p
        ebx = ((state.sp_14 & 3) + (state.sp_18 << 4))*2
        state.sp_30 = state.sp_14 & 3
        ecx = garbage[ebx//2]
        edx = ((state.EAX >> 0x0b) * ecx) & MAXINT
        # 0046801D
        if state.ESI < edx:
            state.EAX = edx
            edx = ((0x800 - ecx) >> 5) + ecx
            ebp += 0xe6c
            garbage[ebx//2] = edx & 0xFFFF
            # 0046804A
            if state.sp_44 or state.sp_14:
                ecx2 = state.out_pos or state.sp_38
                # 3 is sp_58
                ebp += ((decoded[ecx2 - 1] >> (8 - 3)) + ((state.sp_14 & sp_50) << 3)) * 0x600
                state.sp_30 = ebp
            # 0046808F
            if state.sp_18 < 7:
                ecx = 1
                # 0046809F
                while ecx < 0x100:
                    edx = garbage[(ebp//2)+ecx]
                    _pop_byte(state, byte_input)
                    edi = (state.EAX >> 0xb) * edx
                    # 004680C2
                    if state.ESI < edi:
                        state.EAX = edi
                        edi = ((0x800 - edx) >> 5) + edx
                        garbage[(ebp//2)+ecx] = edi & 0xFFFF
                        ecx = ecx * 2
                    # 004680D9
                    else:
                        state.EAX = state.EAX - edi
                        state.ESI = state.ESI - edi
                        edx -= edx >> 5
                        garbage[(ebp//2)+ecx] = edx & 0xFFFF
                        ecx = ecx * 2 + 1
            # 004680FB
            else:
                edi = state.sp_38 if state.out_pos < state.sp_20 else 0
                edi -= state.sp_20
                ebx = 0x100
                edi = decoded[edi + state.out_pos]
                ecx = 1
                tmpvar1 = edi
                # 00468127
                while ecx < 0x100:
                    edi = tmpvar1 * 2
                    tmpvar1 = edi
                    edx = ebx & edi
                    state.sp_4c = state.sp_30 + (edx + ebx + ecx)*2
                    edi = garbage[state.sp_4c//2]
                    # 0046814F
                    _pop_byte(state, byte_input)
                    ebp = (state.EAX >> 0xb) * edi
                    # 00468177
                    if state.ESI < ebp:
                        state.EAX = ebp
                        ebp = ((0x800 - edi) >> 5) + edi
                        garbage[state.sp_4c//2] = ebp & 0xFFFF
                        ecx = ecx * 2
                        edx = ~edx
                    # 00468192
                    else:
                        state.EAX -= ebp
                        state.ESI -= ebp
                        edi = edi - (edi >> 5)
                        garbage[state.sp_4c//2] = edi & 0xFFFF
                        ecx = ecx * 2 + 1
                    ebx = ebx & edx
            # 004681B9
            decoded[state.out_pos] = ecx & 0xFF
            state.out_pos += 1
            state.sp_14 += 1
            state.sp_18 = TABLE_50B8D8[state.sp_18]
            continue
        # 004681E1
        state.EAX -= edx
        state.ESI -= edx
        ecx -= ecx >> 5
        garbage[ebx//2] = ecx & 0xFFFF
        ecx = garbage[(state.sp_18*2 + 0x180)//2]
        # 00468200
        _pop_byte(state, byte_input)
        edx = ((state.EAX >> 0x0b) * ecx) & MAXINT
        # 0046821C
        if state.ESI < edx:
            state.EAX = edx
            edx = ((0x800 - ecx) >> 5) + ecx;
            garbage[(state.sp_18*2 + 0x180)//2] = edx & 0xFFFF
            state.sp_18 += 0x0c
            ecx = 0x664
        # 00468241
        else:
            state.EAX -= edx
            state.ESI -= edx
            ecx -= ecx >> 5
            garbage[(state.sp_18*2 + 0x180)//2] = ecx & 0xFFFF
            # 00468260
            if not state.sp_44 and not state.sp_14:
                return -1
            edx = garbage[(state.sp_18*2 + 0x198)//2]
            # 00468278
            _pop_byte(state, byte_input)
            ecx = (state.EAX >> 0xb) * edx
            # 00468294
            if state.ESI < ecx:
                ebx = ((0x800 - edx) >> 5) + edx
                edx = ((state.sp_18 + 0xf) << 4) + state.sp_30
                garbage[(state.sp_18*2 + 0x198)//2] = ebx & 0xFFFF
                ebx = edx*2
                edx = garbage[ebx//2]
                state.EAX = ecx
                # 004682BF
                _pop_byte(state, byte_input)
                ecx = (state.EAX >> 0xb) * edx
                # 004682E3
                if state.ESI < ecx:
                    ebp = 0 # state.sp_34
                    state.EAX = ecx
                    ecx = ((0x800 - edx) >> 5) + edx
                    edx = state.sp_20
                    garbage[ebx//2] = ecx & 0xFFFF
                    # 00468309
                    ebx = state.sp_38 if state.out_pos < edx else 0
                    ebx = ebx - edx + state.out_pos
                    state.sp_14 += 1
                    decoded[state.out_pos] = decoded[ebx]
                    state.out_pos += 1
                    # 00468322
                    state.sp_18 = 0x9 if state.sp_18 < 7 else 0xB
                    continue
                state.EAX -= ecx
                state.ESI -= ecx
                edx -= edx >> 5
                garbage[ebx//2] = edx & 0xFFFF
            # 00468348
            else:
                state.EAX -= ecx
                state.ESI -= ecx
                edx -= (edx >> 5)
                garbage[(state.sp_18*2+0x198)//2] = edx & 0xFFFF
                ecx = garbage[(state.sp_18*2+0x1B0)//2]
                # 0046836D
                _pop_byte(state, byte_input)
                edx = (state.EAX >> 0xb) * ecx
                # 00468389
                if state.ESI < edx:
                    state.EAX = edx
                    edx = ((0x800 - ecx) >> 5) + ecx
                    ecx = state.sp_28
                    garbage[(state.sp_18*2+0x1B0)//2] = edx & 0xFFFF
                # 004683A5
                else:
                    state.EAX -= edx
                    state.ESI -= edx
                    ecx = ecx - (ecx >> 5)
                    garbage[(state.sp_18*2+0x1B0)//2] = ecx & 0xFFFF
                    ecx = garbage[(state.sp_18*2+0x1C8)//2]
                    # 004683CA
                    _pop_byte(state, byte_input)
                    edx = (state.EAX >> 0xb) * ecx
                    # 004683E1
                    if state.ESI < edx:
                        state.EAX = edx
                        edx = ((0x800 - ecx) >> 5) + ecx
                        ecx = state.sp_2c
                        garbage[(state.sp_18*2+0x1C8)//2] = edx & 0xFFFF
                    # 00468402
                    else:
                        state.EAX -= edx
                        state.ESI -= edx
                        ecx -= ecx >> 5
                        garbage[(state.sp_18*2+0x1C8)//2] = ecx & 0xFFFF
                        ecx = state.sp_40
                        state.sp_40 = state.sp_2c
                    state.sp_2c = state.sp_28
                state.sp_28 = state.sp_20
                state.sp_20 = ecx
            # 00468437
            state.sp_18 = 8 if state.sp_18 < 7 else 0xb
            ecx = 0xA68
        edx = garbage[ecx//2]
        # 0046844f
        _pop_byte(state, byte_input)
        edi = (state.EAX >> 0xb) * edx
        # 0046846B
        if state.ESI < edi:
            ebx = state.sp_30 * 2
            state.EAX = edi
            edi = ((0x800 - edx) >> 5) + edx
            garbage[ecx//2] = edi & 0xFFFF
            ebx = ecx + state.sp_30 * 2 * 8 + 4
            ebp = 0
            state.sp_30 = 8
        # 00468497
        else:
            state.EAX -= edi
            state.ESI -= edi
            edx -= edx >> 5
            garbage[ecx//2] = edx & 0xFFFF
            edx = garbage[(ecx + 2)//2]
            # 004684B3
            _pop_byte(state, byte_input)
            edi = (state.EAX >> 0xb) * edx
            # 004684CF
            if state.ESI < edi:
                ebx = state.sp_30
                state.EAX = edi
                edi = ((0x800 - edx) >> 5) + edx
                garbage[(ecx+2)//2] = edi & 0xFFFF
                ebx = ecx + ebx * 2 * 8 + 0x104
                ebp = 8
                state.sp_30 = 8
            # 004684F9
            else:
                state.EAX -= edi
                state.ESI -= edi
                edx = edx - (edx >> 5)
                garbage[(ecx+2)//2] = edx & 0xFFFF
                ebx = ecx+0x204
                ebp = 0x10
                state.sp_30 = 0x100
        # 0046851D
        edi = 1
        while edi < state.sp_30:
            ecx = garbage[(ebx+edi*2)//2]
            # 00468522
            _pop_byte(state, byte_input)
            edx = (state.EAX >> 0xb) * ecx
            # 0046854A
            if state.ESI < edx:
                state.EAX = edx
                edx = ((0x800 - ecx) >> 5) + ecx
                garbage[(ebx+edi*2)//2] = edx & 0xFFFF
                edi += edi
            # 00468560
            else:
                state.EAX -= edx
                state.ESI -= edx
                ecx = ecx - (ecx >> 5)
                garbage[(ebx+edi*2)//2] = ecx & 0xFFFF
                edi += edi + 1
        # 0046857D
        ebp -= state.sp_30
        edi += ebp
        state.sp_24 = edi
        # 0046858A
        if state.sp_18 >= 0x0c:
            ecx = edi
            # 00468595
            if edi >= 4:
                ecx = 3
            ebp = state.in_pos
            ecx = ((ecx << 7) + 0x360) & MAXINT
            # 004685AE-00468794 (unwound loop)
            tmpvar2 = 1
            while tmpvar2 < 0x40:
                tmpvar2 = tmpvar2 * 2
                edx = garbage[(ecx + tmpvar2)//2]
                _pop_byte(state, byte_input)
                edi = (state.EAX >> 0xb) * edx
                if state.ESI < edi:
                    state.EAX = edi
                    edi = ((0x800 - edx) >> 5) + edx
                    garbage[(tmpvar2+ecx)//2] = edi & 0xFFFF
                else:
                    state.EAX -= edi
                    state.ESI -= edi
                    edx -= edx >> 5
                    garbage[(tmpvar2+ecx)//2] = edx & 0xFFFF
                    tmpvar2 += 1

            ebp = tmpvar2 - 0x40
            # 00468794
            if ebp >= 4:
                edx = ebp
                # edi = 1
                ecx = (ebp >> 1) - 1
                ebp = (ebp & 1) | 2
                state.sp_30 = ecx
                # 004687B3
                if edx < 0x0e:
                    ebp = ebp << (ecx & 0xFF)
                    edi = 1
                    state.sp_40 = 1
                    ecx = ebp - edx
                    ebx = ecx*2+0x55e
                    # 004687CE
                    while state.sp_30:
                        edx = garbage[(ebx+edi*2)//2]
                        # 004687D9
                        _pop_byte(state, byte_input)
                        ecx = (state.EAX >> 0xb) * edx
                        # 004687F8
                        if state.ESI < ecx:
                            state.EAX = ecx
                            ecx = ((0x800 - edx) >> 5) + edx
                            garbage[(ebx+edi*2)//2] = ecx & 0xFFFF
                            edi += edi
                        # 0046880E
                        else:
                            state.EAX -= ecx
                            state.ESI -= ecx
                            edx -= edx >> 5
                            ebp = ebp | state.sp_40
                            garbage[(ebx+edi*2)//2] = edx & 0xFFFF
                            edi += edi + 1
                        state.sp_40 = state.sp_40 << 1
                        state.sp_30 -= 1
                # 00468831
                else:
                    ecx -= 4
                    state.sp_30 = ecx
                    # 00468846
                    while state.sp_30:
                        _pop_byte(state, byte_input)
                        # 00468854
                        state.EAX = state.EAX >> 1
                        state.ESI = (state.ESI - state.EAX) & MAXINT
                        edx = -(state.ESI >> 0x1F)
                        ebp = edx + ebp*2 + 1
                        state.ESI = (state.ESI + (edx & state.EAX)) & MAXINT
                        state.sp_30 -= 1
                    # 0046886D-004689F6 (unwound loop)
                    ebp = ebp << 4
                    tmpvar3 = 1
                    for tmpvar4 in range(4):
                        tmpvar3 = tmpvar3 * 2
                        edx = garbage[(0x644 + tmpvar3)//2]
                        _pop_byte(state, byte_input)
                        edi = (state.EAX >> 0xb) * edx
                        if state.ESI < edi:
                            state.EAX = edi
                            edi = ((0x800 - edx) >> 5) + edx
                            garbage[(0x644 + tmpvar3)//2] = edi & 0xFFFF
                        else:
                            state.EAX -= edi
                            state.ESI -= edi
                            edx -= edx >> 5
                            garbage[(0x644 + tmpvar3)//2] = edx & 0xFFFF
                            ebp = ebp | (1 << tmpvar4)
                            tmpvar3 += 1
                    # 004689F6
                    if ebp == -1:
                        state.sp_24 += 0x112
                        state.sp_18 -= 0x0c
                        break
            # 004689FC
            state.sp_40 = state.sp_2c
            (state.sp_28, state.sp_2c) = (state.sp_20, state.sp_28)
            ecx = state.sp_20
            state.sp_20 = ebp + 1
            # 00468A2B
            if (state.sp_20 and 0 >= state.sp_20) \
                    or 0 >= state.sp_14: # state.garbage_p
                return -3
            # 00468A31
            state.sp_18 = 0x7 if state.sp_18 < 0x13 else 0xa
            edi = state.sp_24

        # 00468A46
        ecx = state.sp_64
        ebp = state.out_pos
        edi += 2
        # 00468A51
        if state.sp_64 == state.out_pos:
            return -4
        ecx -= state.out_pos
        # 00468A5B
        state.sp_30 = min(ecx, edi)
        # 00468A67
        ebx = state.sp_20
        edx = state.sp_38
        # 00468A6F
        ecx = (edx if ebp < ebx else 0) - ebx
        ebx = state.sp_30
        state.sp_14 += state.sp_30
        edi -= state.sp_30
        ecx += ebp
        state.sp_24 = edi
        edi = ecx + ebx
        # 00468A8C
        if edi <= edx:
            edx = 0 # state.sp_34
            ecx -= ebp
            edx += ebp
            ebp += ebx
            edi = ecx
            ecx = edx + ebx
            state.out_pos = ebp
            while edx < ecx:
                ebx = decoded[edi+edx]
                decoded[edx] = ebx
                edx += 1
        # 00468AAB
        else:
            edi = 0 # state.sp_34
            # 00468AAD
            while ebx > 0:
                edx = decoded[ecx+edi]
                decoded[ebp+edi] = edx
                ecx += 1
                ebp += 1
                # 00468ABD
                if ecx == state.sp_38:
                    ecx = 0
                ebx -= 1
            # 00468AC4
            state.out_pos = ebp
    return decoded


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
            if tmp & (1<<29): dy = -dy
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
