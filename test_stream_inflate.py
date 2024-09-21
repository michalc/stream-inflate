import random
import itertools
import zlib
from struct import Struct

import pytest

from stream_inflate import BackwardsTooFar, UnsupportedBlockType, stream_inflate, stream_inflate64


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


def test_stream_inflate_many_fixed_huffman():
    # Manually constructs a deflate stream with more "fixed" huffman values than the cache size,
    # which forces the code to hit certain lines. Not sure a well behaved compressor would ever
    # do this, because it wouldn't bother Huffman encoding so many values, and instead use non
    # compressed blocks
    out = bytearray(100002)
    offset = 0
    bit_offset = 0
    def write_bit(bit):
        nonlocal bit_offset, offset
        if bit_offset == 8:
            offset += 1
            bit_offset = 0
        out[offset] |= (bit << bit_offset)
        bit_offset += 1
    def write_num(num, length):
        # Probably not the most efficient thing in the world
        bit_string = "{0:b}".format(num)
        bit_string = "0" * (length - len(bit_string)) + bit_string
        for bit in reversed(bit_string):
            write_bit(int(bit))

    write_bit(1)       # Final block
    write_num(1, 2)    # Fixed Huffman block

    for _ in range(0, 100000):
        write_num(12, 8)   # Code for zero
    write_num(0, 7)        # Stop code

    out = b''.join(stream_inflate()[0]((out,)))
    assert out == b'\x00' * 100000


def test_unsupported_block_type():
    # Manually constuct a "stream" that has a block type of 3, which is not supported
    # (All 1s in a single byte forces is a quick way to force this: most of the bits are ignored)
    with pytest.raises(UnsupportedBlockType):
        b''.join(stream_inflate()[0]((b'\xFF',)))


def test_stream_inflate_backwards_too_far():
    # Manually constructs a deflate stream that attempts to look backwards too far
    out = bytearray(2)
    offset = 0
    bit_offset = 0
    def write_bit(bit):
        nonlocal bit_offset, offset
        if bit_offset == 8:
            offset += 1
            bit_offset = 0
        out[offset] |= (bit << bit_offset)
        bit_offset += 1
    def write_num(num, length):
        # Probably not the most efficient thing in the world
        bit_string = "{0:b}".format(num)
        bit_string = "0" * (length - len(bit_string)) + bit_string
        for bit in reversed(bit_string):
            write_bit(int(bit))

    write_bit(1)       # Final block
    write_num(1, 2)    # Fixed Huffman block
    write_num(32, 6)   # Code for 258, looking back 1 bytes in stream

    with pytest.raises(BackwardsTooFar):
        b''.join(stream_inflate()[0]((out,)))


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
