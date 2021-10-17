from struct import Struct


def stream_inflate(deflate_chunks, chunk_size=65536):
    b_len_struct = Struct('<H')

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

                out[out_offset_bit // 8] |= chunk[offset_byte] & (2 ** offset_bit)

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

    def upcompressed(get_bits, get_bytes, yield_bytes):
        b_final = b'\0'

        while not b_final[0]:
            b_final = get_bits(1)
            b_type = get_bits(2)
            b_len, = b_len_struct.unpack(get_bytes(2))
            get_bytes(2)
            yield from yield_bytes(b_len)

    get_bits, get_bytes, yield_bytes = get_readers(deflate_chunks)
    yield from upcompressed(get_bits, get_bytes, yield_bytes)


class TruncatedDataError():
    pass
