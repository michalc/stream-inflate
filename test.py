import random
import itertools
import unittest
import zlib
from struct import Struct

from stream_inflate import UnsupportedBlockType, stream_inflate, stream_inflate64


class TestStreamInflate(unittest.TestCase):

    def test_stream_inflate(self):
        rnd = random.Random()

        strategies = [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED]
        levels = [-1, 0, 9]
        base_data_lens = [8, 800, 80000]
        num_repeats = [0, 1, 2, 100]
        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        last_index = 0
        last_chunk = None
        def content(input_size):
            nonlocal last_index, last_chunk

            for i in range(0, len(stream), input_size):
                last_index = i + input_size
                last_chunk = stream[i:i + input_size]
                yield last_chunk

        for strategy, level, base_data_len, num_repeats, input_size, output_size in itertools.product(strategies, levels, base_data_lens, num_repeats, input_sizes, output_sizes):
            with \
                self.subTest(
                        strategy=strategy,
                        level=level,
                        base_data_len=base_data_len,
                        num_repeat=num_repeats,
                        input_size=input_size,
                        output_size=output_size,
                ):

                rnd.seed(1)
                data = rnd.getrandbits(base_data_len).to_bytes(base_data_len//8, byteorder='big') * num_repeats
                compressobj = zlib.compressobj(level=level, wbits=-zlib.MAX_WBITS, strategy=strategy)
                stream = compressobj.compress(data) + compressobj.flush() + b'Unconsumed'

                # Make sure it really is DEFLATEd
                self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data)

                chunks, get_end_index = stream_inflate(content(input_size), chunk_size=output_size)
                uncompressed = b''.join(chunks)
                self.assertEqual(uncompressed, data)
                self.assertEqual(last_chunk[get_end_index():] + stream[last_index:], b'Unconsumed')

    def test_stream_inflate64(self):
        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        with open('fixtures/data64.bin', 'rb') as f:
            data = f.read()

        def content(input_size):
            offset = 0
            with open('fixtures/deflate64.bin', 'rb') as f:
                while True:
                    chunk = f.read(input_size)
                    if not chunk:
                        break
                    yield chunk

        for input_size, output_size in itertools.product(input_sizes, output_sizes):
            with \
                self.subTest(
                        input_size=input_size,
                        output_size=output_size,
                ):

                uncompressed = b''.join(stream_inflate64(content(input_size), chunk_size=output_size)[0])
                self.assertEqual(uncompressed, data)
