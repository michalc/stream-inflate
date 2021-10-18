import random
import itertools
import unittest
import zlib
from struct import Struct

from stream_inflate import UnsupportedBlockType, stream_inflate


class TestStreamInflate(unittest.TestCase):

    def test_stream_inflate(self):
        rnd = random.Random()

        strategies = [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED]
        levels = [-1, 0, 9]
        base_data_lens = [8, 800, 80000]
        num_repeats = [0, 1, 2, 100]
        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        def content(input_size):
            for i in range(0, len(stream), input_size):
                yield stream[i:i + input_size]

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
                stream = compressobj.compress(data) + compressobj.flush()

                # Make sure it really is DEFLATEd
                self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data)

                uncompressed = b''.join(stream_inflate(content(input_size), chunk_size=output_size))
                self.assertEqual(uncompressed, data)
