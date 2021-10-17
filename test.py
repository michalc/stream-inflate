import itertools
import unittest
import zlib
from struct import Struct

from stream_inflate import stream_inflate


class TestStreamInflate(unittest.TestCase):

    def test_uncompressed_block(self):
        b_len_struct = Struct('<H')
        data = b'Some uncompressed bytes'
        stream = \
            b'\0' + \
            Struct('<H').pack(len(data)) + \
            Struct('<H').pack(65535 - len(data)) + \
            data + \
            b'\1' + \
            Struct('<H').pack(len(data)) + \
            Struct('<H').pack(65535 - len(data)) + \
            data

        input_sizes = [1, 7, 65536]
        output_sizes = [1, 7, 65536]

        def content(input_size):
            for i in range(0, len(stream), input_size):
                yield stream[i:i + input_size]

        # Make sure it really is DEFLATEd
        self.assertEqual(zlib.decompress(stream, wbits=-zlib.MAX_WBITS), data * 2)

        for input_size, output_size in itertools.product(input_sizes, output_sizes):
            with self.subTest(input_size=input_size, output_size=output_size):
                uncompressed = b''.join(stream_inflate(content(input_size), chunk_size=output_size))
                self.assertEqual(uncompressed, data * 2)
