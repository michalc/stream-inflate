import itertools
import unittest
import zlib
from struct import Struct

from stream_inflate import UnsupportedBlockType, stream_inflate


class TestStreamInflate(unittest.TestCase):

    def test_stream_inflate(self):
        b_len_struct = Struct('<H')
        base_data = b'Some uncompressed bytes'

        strategy_levels = [
            (zlib.Z_DEFAULT_STRATEGY, 0),
            (zlib.Z_FIXED, -1),
        ]
        num_repeats = [0, 1, 3, 10000]
        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        def content(input_size):
            for i in range(0, len(stream), input_size):
                yield stream[i:i + input_size]

        for (strategy, level), num_repeats, input_size, output_size in itertools.product(strategy_levels, num_repeats, input_sizes, output_sizes):
            with \
                self.subTest(
                        strategy=strategy,
                        level=level,
                        num_repeat=num_repeats,
                        input_size=input_size,
                        output_size=output_size,
                ):
                data = base_data * num_repeats
                compressobj = zlib.compressobj(level=level, wbits=-zlib.MAX_WBITS, strategy=strategy)
                stream = compressobj.compress(data) + compressobj.flush()

                # Make sure it really is DEFLATEd
                self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data)

                uncompressed = b''.join(stream_inflate(content(input_size), chunk_size=output_size))
                self.assertEqual(uncompressed, data)

    def test_zlib_compressed(self):
        b_len_struct = Struct('<H')

        data = b'Some uncompressed bytes' * 1000
        compressobj = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        stream = compressobj.compress(data) + compressobj.flush()

        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        def content(input_size):
            for i in range(0, len(stream), input_size):
                yield stream[i:i + input_size]

        # # Make sure it really is DEFLATEd
        self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data)

        for input_size, output_size in itertools.product(input_sizes, output_sizes):
            with self.subTest(input_size=input_size, output_size=output_size):
                with self.assertRaises(UnsupportedBlockType):
                    b''.join(stream_inflate(content(input_size), chunk_size=output_size))
