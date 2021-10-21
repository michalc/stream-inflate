from collections import Counter, defaultdict
from struct import Struct


def stream_inflate(deflate_chunks, chunk_size=65536):
    length_extra_bits_diffs = (
        (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
        (1, 11), (1, 13), (1, 15), (1, 17),
        (2, 19), (2, 23), (2, 27), (2, 31),
        (3, 35), (3, 43), (3, 51), (3, 59),
        (4, 67), (4, 83), (4, 99), (4, 115),
        (5, 131), (5, 163), (5, 195), (5, 227),
        (0, 258),
    )
    dist_extra_bits_diffs = (
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 5), (1, 7), (2, 9), (2, 13),
        (3, 17), (3, 25), (4, 33), (4, 49),
        (5, 65), (5, 97), (6, 129), (6, 193),
        (7, 257), (7, 385), (8, 513), (8, 769),
        (9, 1025), (9, 1537), (10, 2049), (10, 3073),
        (11, 4097), (11, 6145), (12, 8193), (12, 12289),
        (13, 16385), (13, 24577),
    )
    cache_size = 32768
    return _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, deflate_chunks, chunk_size)


def stream_inflate64(deflate_chunks, chunk_size=65536):
    length_extra_bits_diffs = (
        (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
        (1, 11), (1, 13), (1, 15), (1, 17),
        (2, 19), (2, 23), (2, 27), (2, 31),
        (3, 35), (3, 43), (3, 51), (3, 59),
        (4, 67), (4, 83), (4, 99), (4, 115),
        (5, 131), (5, 163), (5, 195), (5, 227),
        (16, 3),
    )
    dist_extra_bits_diffs = (
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 5), (1, 7), (2, 9), (2, 13),
        (3, 17), (3, 25), (4, 33), (4, 49),
        (5, 65), (5, 97), (6, 129), (6, 193),
        (7, 257), (7, 385), (8, 513), (8, 769),
        (9, 1025), (9, 1537), (10, 2049), (10, 3073),
        (11, 4097), (11, 6145), (12, 8193), (12, 12289),
        (13, 16385), (13, 24577), (14, 32769), (14, 49153),
    )
    cache_size = 65536
    return _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, deflate_chunks, chunk_size)

def _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, deflate_chunks, chunk_size):
    literal_stop_or_length_code_lengths = \
        (8,) * 144 + \
        (9,) * 112 + \
        (7,) * 24 + \
        (8,) * 8
    dist_code_lengths = \
        (5,) * 32
    code_lengths_alphabet = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)

    def get_readers(iterable):
        chunk = b''
        offset_byte = 0
        offset_bit = 0
        it = iter(iterable)

        def _next_or_truncated_error():
            try:
                return next(it)
            except StopIteration:
                raise TruncatedDataError from None

        def _get_bits(num_bits):
            nonlocal chunk, offset_byte, offset_bit

            out = bytearray(-(-num_bits // 8))
            out_offset_bit = 0

            while num_bits:
                if offset_bit == 8:
                    offset_bit = 0
                    offset_byte += 1

                if offset_byte == len(chunk):
                    chunk = _next_or_truncated_error()
                    offset_byte = 0

                out[out_offset_bit // 8] |= (chunk[offset_byte] & (2 ** offset_bit)) >> offset_bit << (out_offset_bit % 8)

                num_bits -= 1
                offset_bit += 1
                out_offset_bit += 1

            return bytes(out)

        def _yield_bytes(num_bytes):
            nonlocal chunk, offset_byte, offset_bit

            if offset_bit:
                offset_byte += 1
            offset_bit = 0

            while num_bytes:
                if offset_byte == len(chunk):
                    chunk = _next_or_truncated_error()
                    offset_byte = 0
                to_yield = min(num_bytes, len(chunk) - offset_byte)
                offset_byte += to_yield
                num_bytes -= to_yield
                yield chunk[offset_byte - to_yield:offset_byte]

        def _get_bytes(num_bytes):
            return b''.join(_yield_bytes(num_bytes))

        def _get_end_index():
            return offset_byte + (1 if offset_bit else 0)

        return _get_bits, _get_bytes, _yield_bytes, _get_end_index

    def get_backwards_cache(size):
        cache = bytearray(size)
        cache_start = 0
        cache_len = 0

        def via_cache(bytes_iter):
            nonlocal cache, cache_start, cache_len

            for chunk in bytes_iter:
                chunk_start = max(len(chunk) - size, 0)
                chunk_end = len(chunk)
                chunk_len = chunk_end - chunk_start
                part_1_start = (cache_start + cache_len) % size
                part_1_end = min(part_1_start + chunk_len, size)
                part_1_chunk_start = chunk_start
                part_1_chunk_end = chunk_start + (part_1_end - part_1_start)
                part_2_start = 0
                part_2_end = chunk_len - (part_1_end - part_1_start)
                part_2_chunk_start = part_1_chunk_end
                part_2_chunk_end = part_1_chunk_end + (part_2_end - part_2_start)

                cache_len_over_size = max((cache_len + chunk_len) - size, 0)
                cache_len = min(size, cache_len + chunk_len)
                cache_start = (cache_start + cache_len_over_size) % size

                cache[part_1_start:part_1_end] = chunk[part_1_chunk_start:part_1_chunk_end]
                cache[part_2_start:part_2_end] = chunk[part_2_chunk_start:part_2_chunk_end]

                yield chunk

        def from_cache(dist, length):
            if dist > cache_len:
                raise Exception('Searching backwards too far', dist, len(cache))

            available = dist
            part_1_start = (cache_start + cache_len - dist) % size
            part_1_end = min(part_1_start + available, size)
            part_2_start = 0
            part_2_end = max(available - (part_1_end - part_1_start), 0)

            while length:
                to_yield = cache[part_1_start:part_1_end][:length]
                yield to_yield
                length -= len(to_yield)

                to_yield = cache[part_2_start:part_2_end][:length]
                yield to_yield
                length -= len(to_yield)

        return via_cache, from_cache

    def get_huffman_decoder(get_bits, lengths):

        def yield_codes():
            max_bits = max(lengths)
            bl_count = defaultdict(int, Counter(lengths))
            next_code = {}
            code = 0
            bl_count[0] = 0
            for bits in range(1, max_bits + 1):
                 code = (code + bl_count[bits - 1]) << 1;
                 next_code[bits] = code

            for value, length in enumerate(lengths):
                if length != 0:
                    yield (length, next_code[length]), value
                    next_code[length] += 1

        def get_next():
            length = 0
            code = 0
            while True:
                length += 1
                code = (code << 1) | ord(get_bits(1))
                try:
                    return codes[(length, code)]
                except KeyError:
                    continue

        codes = dict(yield_codes())

        return get_next

    def get_code_lengths(get_bits, get_code_length_code, num_codes):
        i = 0
        previous = None
        while i < num_codes:
            code = get_code_length_code()
            if code < 16:
                previous = code
                i += 1
                yield code
            elif code == 16:
                repeat = 3 + ord(get_bits(2))
                i += repeat
                for _ in range(0, repeat):
                    yield previous
            elif code == 17:
                repeat = 3 + ord(get_bits(3))
                i += repeat
                previous = 0
                for _ in range(0, repeat):
                    yield 0
            elif code == 18:
                repeat = 11 + ord(get_bits(7))
                i += repeat
                previous = 0
                for _ in range(0, repeat):
                    yield 0

    def upcompress(get_bits, get_bytes, yield_bytes, via_cache, from_cache):
        b_final = b'\0'

        while not b_final[0]:
            b_final = get_bits(1)
            b_type = get_bits(2)

            if b_type == '\3':
                raise UnsupportedBlockType(b_type)

            if b_type == b'\0':
                b_len = int.from_bytes(get_bytes(2), byteorder='little')
                get_bytes(2)
                yield from via_cache(yield_bytes(b_len))
                continue

            if b_type == b'\1':
                get_literal_stop_or_length_code = get_huffman_decoder(get_bits, literal_stop_or_length_code_lengths)
                get_backwards_dist_code = get_huffman_decoder(get_bits, dist_code_lengths)
            else:
                num_literal_length_codes = ord(get_bits(5)) + 257
                num_dist_codes = ord(get_bits(5)) + 1
                num_length_codes = ord(get_bits(4)) + 4

                code_length_code_lengths = tuple(ord(get_bits(3)) for _ in range(0, num_length_codes)) + ((0,) * (19 - num_length_codes))
                code_length_code_lengths = tuple(
                    v for i, v in
                    sorted(enumerate(code_length_code_lengths), key=lambda x: code_lengths_alphabet[x[0]])
                )
                get_code_length_code = get_huffman_decoder(get_bits, code_length_code_lengths)

                dynamic_code_lengths = tuple(get_code_lengths(get_bits, get_code_length_code, num_literal_length_codes + num_dist_codes))
                dynamic_literal_code_lengths = dynamic_code_lengths[:num_literal_length_codes]
                dynamic_dist_code_lengths = dynamic_code_lengths[num_literal_length_codes:]

                get_literal_stop_or_length_code = get_huffman_decoder(get_bits, dynamic_literal_code_lengths)
                get_backwards_dist_code = get_huffman_decoder(get_bits, dynamic_dist_code_lengths)

            while True:
                literal_stop_or_length_code = get_literal_stop_or_length_code()
                if literal_stop_or_length_code < 256:
                    yield from via_cache((bytes((literal_stop_or_length_code,)),))
                elif literal_stop_or_length_code == 256:
                    break
                else:
                    length_extra_bits, length_diff = length_extra_bits_diffs[literal_stop_or_length_code - 257]
                    length_extra = int.from_bytes(get_bits(length_extra_bits), byteorder='little')

                    code = get_backwards_dist_code()
                    dist_extra_bits, dist_diff = dist_extra_bits_diffs[code]
                    dist_extra = int.from_bytes(get_bits(dist_extra_bits), byteorder='little')

                    yield from via_cache(from_cache(dist=dist_extra + dist_diff, length=length_extra + length_diff))

    def paginate(bytes_iter, page_size):
        chunk = b''
        offset = 0
        it = iter(bytes_iter)

        def up_to_page_size(num):
            nonlocal chunk, offset

            while num:
                if offset == len(chunk):
                    try:
                        chunk = next(it)
                    except StopIteration:
                        break
                    else:
                        offset = 0
                to_yield = min(num, len(chunk) - offset)
                offset = offset + to_yield
                num -= to_yield
                yield chunk[offset - to_yield:offset]

        while True:
            page = b''.join(up_to_page_size(page_size))
            if not page:
                break
            yield page

    get_bits, get_bytes, yield_bytes, get_end_index = get_readers(deflate_chunks)
    via_cache, from_cache = get_backwards_cache(cache_size)

    uncompressed = upcompress(get_bits, get_bytes, yield_bytes, via_cache, from_cache)
    return paginate(uncompressed, chunk_size), get_end_index

class TruncatedDataError(Exception):
    pass

class UnsupportedBlockType(Exception):
    pass
