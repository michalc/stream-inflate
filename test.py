import random
import itertools
import unittest
import zlib
from struct import Struct

from stream_inflate import stream_inflate, stream_inflate64


class TestStreamInflate(unittest.TestCase):

    def test_stream_inflate(self):
        rnd = random.Random()

        strategies = [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED]
        levels = [-1, 0, 9]
        base_data_lens = [8, 800, 80000]
        num_repeats = [0, 1, 2, 100]
        input_sizes = [1, 7, 65536]
        suspend_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        total_attempted_consumed = 0

        def content(stream, input_size):
            nonlocal total_attempted_consumed

            for i in range(0, len(stream), input_size):
                chunk = stream[i:i + input_size]
                total_attempted_consumed += len(chunk)
                yield chunk

        def compressed_iters(stream, input_size, suspend_size):
            for i in range(0, len(stream), suspend_size):
                yield content(stream[i:i + suspend_size], input_size)

        for strategy, level, base_data_len, num_repeats, input_size, suspend_size, output_size in itertools.product(strategies, levels, base_data_lens, num_repeats, input_sizes, suspend_sizes, output_sizes):
            with \
                self.subTest(
                        strategy=strategy,
                        level=level,
                        base_data_len=base_data_len,
                        num_repeat=num_repeats,
                        input_size=input_size,
                        suspend_size=suspend_size,
                        output_size=output_size,
                ):
                print('.', end='', flush=True)

                rnd.seed(1)
                data = rnd.getrandbits(base_data_len).to_bytes(base_data_len//8, byteorder='big') * num_repeats
                compressobj = zlib.compressobj(level=level, wbits=-zlib.MAX_WBITS, strategy=strategy)
                stream = compressobj.compress(data) + compressobj.flush() + b'Unconsumed'

                # Make sure it really is DEFLATEd
                self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data)

                total_attempted_consumed = 0
                uncompress, is_done, num_bytes_unconsumed = stream_inflate(chunk_size=output_size)
                uncompressed = b''
                iters = compressed_iters(stream, input_size, suspend_size)
                while not is_done():
                    uncompressed += b''.join(uncompress(next(iters)))


                self.assertEqual(uncompressed, data)
                self.assertEqual(stream[total_attempted_consumed - num_bytes_unconsumed():], b'Unconsumed')

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
                print('.', end='', flush=True)

                uncompressed = b''.join(stream_inflate64(chunk_size=output_size)[0](content(input_size)))
                self.assertEqual(uncompressed, data)
