from collections import Counter, defaultdict
from struct import Struct


def stream_inflate(deflate_chunks, chunk_size=65536):
    b_len_struct = Struct('<H')
    fixed_lengths = \
        [8] * 144 + \
        [9] * 112 + \
        [7] * 24 + \
        [8] * 8
    fixed_distances = \
        [5] * 32

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
                to_yield = min(num_bytes, len(chunk) - offset_byte, chunk_size)
                offset_byte += to_yield
                num_bytes -= to_yield
                yield chunk[offset_byte - to_yield:offset_byte]

        def _get_bytes(num_bytes):
            return b''.join(_yield_bytes(num_bytes))

        return _get_bits, _get_bytes, _yield_bytes

    def get_backwards_cache(size):
        cache = b''

        def via_cache(bs):
            nonlocal cache
            cache = (cache + bs)[:size]
            return bs

        def from_cache(backwards_dist, length):
            return cache[-backwards_dist:- backwards_dist + length]

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

    def upcompressed(get_bits, get_bytes, yield_bytes, into_cache, from_cache):
        b_final = b'\0'

        while not b_final[0]:
            b_final = get_bits(1)
            b_type = get_bits(2)
            if b_type == b'\0':
                b_len, = b_len_struct.unpack(get_bytes(2))
                get_bytes(2)
                yield from yield_bytes(b_len)
            elif b_type == b'\1':
                get_next = get_huffman_decoder(get_bits, fixed_lengths)
                get_next_length = get_huffman_decoder(get_bits, fixed_distances)
                while True:
                    value = get_next()
                    if value < 256:
                        yield via_cache(chr(value).encode())
                    elif value == 256:
                        break
                    else:
                        extra_bits, diff = \
                            (0, -254) if value < 265 else \
                            (1, -254) if value < 269 else \
                            (2, -250) if value < 273 else \
                            (3, -238) if value < 277 else \
                            (4, -210) if value < 281 else \
                            (5, -150) if value < 285 else \
                            (0, -27)
                        extra = int.from_bytes(get_bits(extra_bits), byteorder='big')
                        length = value + diff + extra
                        backward_dist_code = get_next_length()
                        extra_bits, diff = \
                            (0, 1) if backward_dist_code < 4 else \
                            (1, 1) if backward_dist_code < 6 else \
                            (2, 3) if backward_dist_code < 8 else \
                            (3, 9) if backward_dist_code < 10 else \
                            (4, 23) if backward_dist_code < 12 else \
                            (5, 53) if backward_dist_code < 14 else \
                            (6, 115) if backward_dist_code < 16 else \
                            (7, 241) if backward_dist_code < 18 else \
                            (8, 495) if backward_dist_code < 20 else \
                            (9, 1005) if backward_dist_code < 22 else \
                            (10, 2027) if backward_dist_code < 24 else \
                            (11, 4073) if backward_dist_code < 26 else \
                            (12, 8167) if backward_dist_code < 28 else \
                            (13, 16357)
                        extra_raw = get_bits(extra_bits)
                        extra = int.from_bytes(extra_raw, byteorder='big')
                        backwards_dist = backward_dist_code + diff + extra
                        yield via_cache(from_cache(backwards_dist, length))
            else:
                raise UnsupportedBlockType(b_type)

    get_bits, get_bytes, yield_bytes = get_readers(deflate_chunks)
    via_cache, from_cache = get_backwards_cache(32768)
    yield from upcompressed(get_bits, get_bytes, yield_bytes, via_cache, from_cache)


class TruncatedDataError(Exception):
    pass

class UnsupportedBlockType(Exception):
    pass
