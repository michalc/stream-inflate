import random
import itertools
import zlib
from struct import Struct

import pytest

from stream_inflate import stream_inflate, stream_inflate64


@pytest.mark.parametrize("strategy", [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED])
@pytest.mark.parametrize("level", [-1, 0, 9])
@pytest.mark.parametrize("base_data_len", [8, 800, 80000])
@pytest.mark.parametrize("num_repeats", [0, 1, 2, 100])
@pytest.mark.parametrize("input_size", [1, 7, 65536])
@pytest.mark.parametrize("suspend_size", [1, 7, 65536])
@pytest.mark.parametrize("output_size", [1, 7, 65536])
def test_stream_inflate(strategy, level, base_data_len, num_repeats, input_size, suspend_size, output_size):
    rnd = random.Random()

    total_attempted_consumed = 0

    def content(stream, input_size):
        nonlocal total_attempted_consumed

        for i in range(0, len(stream), input_size):
            chunk = stream[i:i + input_size]
            total_attempted_consumed += len(chunk)
            yield chunk

    def compressed_iters(stream, input_size, suspend_size):
        return (
            content(stream[i:i + suspend_size], input_size)
            for i in range(0, len(stream), suspend_size)
        )

    rnd.seed(1)
    data = rnd.getrandbits(base_data_len).to_bytes(base_data_len//8, byteorder='big') * num_repeats
    compressobj = zlib.compressobj(level=level, wbits=-zlib.MAX_WBITS, strategy=strategy)
    stream = compressobj.compress(data) + compressobj.flush() + b'Unconsumed'

    # Make sure it really is DEFLATEd
    assert zlib.decompress(stream, wbits=-zlib.MAX_WBITS) == data

    uncompress, is_done, num_bytes_unconsumed = stream_inflate(chunk_size=output_size)
    uncompressed = b''
    iters = iter(compressed_iters(stream, input_size, suspend_size))
    while not is_done():
        uncompressed += b''.join(uncompress(next(iters)))

    assert uncompressed == data
    assert stream[total_attempted_consumed - num_bytes_unconsumed():] == b'Unconsumed'

    # Exhaust iters for code coverage reasons
    for _ in iters: pass

@pytest.mark.parametrize("input_size", [1, 7, 65536])
@pytest.mark.parametrize("output_size", [1, 7, 65536])
def test_stream_inflate64(input_size, output_size):
    with open('fixtures/data64.bin', 'rb') as f:
        data = f.read()

    def content(input_size):
        offset = 0
        with open('fixtures/deflate64.bin', 'rb') as f:
            yield from iter(lambda: f.read(input_size), b'')

    uncompressed = b''.join(stream_inflate64(chunk_size=output_size)[0](content(input_size)))
    assert uncompressed == data
