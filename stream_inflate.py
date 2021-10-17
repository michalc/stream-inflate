from collections import Counter, defaultdict
from struct import Struct


def stream_inflate(deflate_chunks, chunk_size=65536):
    b_len_struct = Struct('<H')
    fixed_lengths = \
        [8] * 144 + \
        [9] * 112 + \
        [7] * 24 + \
        [8] * 8

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

    def upcompressed(get_bits, get_bytes, yield_bytes):
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
                while True:
                    value = get_next()
                    if value == 256:
                        break
                    yield chr(value).encode()
            else:
                raise UnsupportedBlockType(b_type)

    get_bits, get_bytes, yield_bytes = get_readers(deflate_chunks)
    yield from upcompressed(get_bits, get_bytes, yield_bytes)


class TruncatedDataError(Exception):
    pass

class UnsupportedBlockType(Exception):
    pass
