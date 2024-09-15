from collections import Counter, defaultdict, namedtuple


def stream_inflate(chunk_size=65536):
    length_extra_bits_diffs = (
        (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
        (1, 11), (1, 13), (1, 15), (1, 17),
        (2, 19), (2, 23), (2, 27), (2, 31),
        (3, 35), (3, 43), (3, 51), (3, 59),
        (4, 67), (4, 83), (4, 99), (4, 115),
        (5, 131), (5, 163), (5, 195), (5, 227),
        (0, 258),
    )
    dist_extra_bits_diffs = (
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 5), (1, 7), (2, 9), (2, 13),
        (3, 17), (3, 25), (4, 33), (4, 49),
        (5, 65), (5, 97), (6, 129), (6, 193),
        (7, 257), (7, 385), (8, 513), (8, 769),
        (9, 1025), (9, 1537), (10, 2049), (10, 3073),
        (11, 4097), (11, 6145), (12, 8193), (12, 12289),
        (13, 16385), (13, 24577),
    )
    cache_size = 32768
    return _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, chunk_size)


def stream_inflate64(chunk_size=65536):
    length_extra_bits_diffs = (
        (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
        (1, 11), (1, 13), (1, 15), (1, 17),
        (2, 19), (2, 23), (2, 27), (2, 31),
        (3, 35), (3, 43), (3, 51), (3, 59),
        (4, 67), (4, 83), (4, 99), (4, 115),
        (5, 131), (5, 163), (5, 195), (5, 227),
        (16, 3),
    )
    dist_extra_bits_diffs = (
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 5), (1, 7), (2, 9), (2, 13),
        (3, 17), (3, 25), (4, 33), (4, 49),
        (5, 65), (5, 97), (6, 129), (6, 193),
        (7, 257), (7, 385), (8, 513), (8, 769),
        (9, 1025), (9, 1537), (10, 2049), (10, 3073),
        (11, 4097), (11, 6145), (12, 8193), (12, 12289),
        (13, 16385), (13, 24577), (14, 32769), (14, 49153),
    )
    cache_size = 65536
    return _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, chunk_size)


def _stream_inflate(length_extra_bits_diffs, dist_extra_bits_diffs, cache_size, chunk_size):
    literal_stop_or_length_code_lengths = \
        (8,) * 144 + \
        (9,) * 112 + \
        (7,) * 24 + \
        (8,) * 8
    dist_code_lengths = \
        (5,) * 32
    code_lengths_alphabet = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)

    # An object that can be seen as a "deferred" that can pause a generator, with
    # the extra abiliy to yield values by the generator "runner".
    DeferredYielder = namedtuple('DeferredYielder', (
        'can_proceed',
        'to_yield',
        'return_value',
    ))
    def _true():
        return True
    def _none():
        return None

    def get_iterable_queue():
        next_it = None
        it = None

        def _append(iterable):
            nonlocal next_it
            next_it = iterable

        def _next():
            nonlocal next_it, it

            while True:
                if it is None:
                    if next_it is None:
                        raise StopIteration() from None
                    it = iter(next_it)
                    next_it = None

                try:
                    return next(it)
                except StopIteration:
                    it = None

        return _append, _next

    # Low level bit/byte readers
    def get_readers(it_next):
        chunk = b''
        offset_byte = 0
        offset_bit = 0

        def _has_bit():
            nonlocal chunk, offset_byte, offset_bit

            if offset_bit == 8:
                offset_bit = 0
                offset_byte += 1

            if offset_byte == len(chunk):
                try:
                    chunk = memoryview(it_next())
                except StopIteration:
                    return False
                else:
                    offset_byte = 0
                    offset_bit = 0

            return True

        def _has_byte():
            nonlocal chunk, offset_byte, offset_bit

            if offset_bit:
                offset_byte += 1
            offset_bit = 0

            return _has_bit()

        def _get_bit():
            nonlocal offset_bit
            offset_bit += 1

            return (chunk[offset_byte] & (2 ** (offset_bit - 1))) >> (offset_bit - 1)

        def _get_byte():
            nonlocal offset_byte
            offset_byte += 1
            return chunk[offset_byte - 1]

        def _yield_bytes_up_to(num):
            nonlocal chunk, offset_byte, offset_bit

            if offset_bit:
                offset_byte += 1
            offset_bit = 0

            while num:
                if offset_byte == len(chunk):
                    try:
                        chunk = memoryview(it_next())
                    except StopIteration:
                        return
                    offset_byte = 0
                to_yield = min(num, len(chunk) - offset_byte)
                offset_byte += to_yield
                num -= to_yield
                yield chunk[offset_byte - to_yield:offset_byte]

        def _num_bytes_unconsumed():
            return len(chunk) - offset_byte - (1 if offset_bit else 0)

        return _has_bit, _has_byte, _get_bit, _get_byte, _yield_bytes_up_to, _num_bytes_unconsumed

    # Bit/byte readers that are DeferredYielder
    def get_deferred_yielder_readers(reader_has_bit, reader_has_byte, reader_get_bit, reader_get_byte, reader_yield_bytes_up_to):

        get_bit = DeferredYielder(can_proceed=reader_has_bit, to_yield=None, return_value=reader_get_bit)
        get_byte = DeferredYielder(can_proceed=reader_has_byte, to_yield=None, return_value=reader_get_byte)

        def get_bits(num_bits):
            out = 0
            out_offset_bit = 0

            for out_offset_bit in range(0, num_bits):
                out |= (reader_get_bit() if reader_has_bit() else (yield get_bit)) << out_offset_bit

            return out

        def get_bits_as_bytes(num_bits):
            out = bytearray(-(-num_bits // 8))
            out_offset_bit = 0

            while num_bits:
                bit = (reader_get_bit() if reader_has_bit() else (yield get_bit))
                out[out_offset_bit // 8] |= bit << (out_offset_bit % 8)

                num_bits -= 1
                out_offset_bit += 1

            return bytes(out)

        def get_bytes(num_bytes):
            out = bytearray(num_bytes)
            out_offset = 0

            while out_offset != num_bytes:
                out[out_offset] = (reader_get_byte() if reader_has_byte() else (yield get_byte))
                out_offset += 1

            return bytes(out)

        return get_bit, get_bits, get_bits_as_bytes, get_bytes

    def paginate(get_bytes_iter, page_size):

        def _paginate(bytes_iter):
            chunk = b''
            offset = 0
            it = iter(bytes_iter)

            def up_to_page_size(num):
                nonlocal chunk, offset

                while num:
                    if offset == len(chunk):
                        try:
                            chunk = next(it)
                        except StopIteration:
                            break
                        else:
                            offset = 0
                    to_yield = min(num, len(chunk) - offset)
                    offset = offset + to_yield
                    num -= to_yield
                    yield chunk[offset - to_yield:offset]

            while True:
                page = b''.join(up_to_page_size(page_size))
                if not page:
                    break
                yield page

        def _run(*args, **kwargs):
            yield from _paginate(get_bytes_iter(*args, **kwargs))

        return _run

    def inflate(get_bit, get_bits, get_bits_as_bytes, get_bytes, reader_yield_bytes_up_to):

        def via_cache(bytes_iter):
            nonlocal cache_end, cache_len

            for chunk in bytes_iter:
                chunk_len = _len(chunk)
                cacheable_chunk_len = chunk_len if chunk_len < cache_size else cache_size
                chunk_start = chunk_len - cacheable_chunk_len
                part_1_len = (cache_size - cache_end) if (cache_size - cache_end) < cacheable_chunk_len else cacheable_chunk_len
                part_2_len = cacheable_chunk_len - part_1_len

                cache[cache_end:cache_end + part_1_len] = chunk[chunk_start:chunk_start + part_1_len]
                cache_end = (cache_end + part_1_len) % cache_size

                if part_2_len:
                    cache[cache_end:cache_end + part_2_len] = chunk[chunk_start + part_1_len:chunk_start + part_1_len + part_2_len]
                    cache_end = (cache_end + part_2_len) % cache_size

                cache_len = (cache_len + cacheable_chunk_len) if (cache_len + cacheable_chunk_len) < cache_size else cache_size

                yield chunk

        def from_cache(dist, length):
            if dist > cache_len:
                raise Exception('Searching backwards too far', dist, _len(cache))

            min_length_dist = dist if dist < length else length
            part_1_start = (cache_end - dist) % cache_size
            part_1_end = (part_1_start + min_length_dist) if (part_1_start + min_length_dist) < cache_size else cache_size
            part_2_start = 0
            part_2_end = min_length_dist - (part_1_end - part_1_start)

            parts = cache[part_1_start:part_1_end] + cache[part_2_start:part_2_end]
            len_parts = _len(parts)

            num_repeats = length // len_parts
            extra = length - num_repeats * len_parts

            yield parts * num_repeats + parts[:extra]

        def get_huffman_codes(lengths):

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
                        next_code[length] += 1
                        yield (length, next_code[length] - 1), value

            return dict(yield_codes())

        def get_huffman_value(codes):
            length = 0
            code = 0
            while True:
                length += 1
                code = (code << 1) | (reader_get_bit() if reader_has_bit() else (yield get_bit))
                value = codes.get((length, code))
                if value is not None:
                    return value

        def get_code_length_code_lengths(num_length_codes):
            result = [0] * num_length_codes
            for i in range(0, num_length_codes):
                result[i] = (yield from get_bits(3))
            return tuple(result)

        def get_code_lengths(code_length_codes, num_codes):
            result = [0] * num_codes

            i = 0
            previous = None
            while i < num_codes:
                code = yield from get_huffman_value(code_length_codes)
                if code < 16:
                    previous = code
                    result[i] = code
                    i += 1
                elif code == 16:
                    for _ in range(0, 3 + (yield from get_bits(2))):
                        result[i] = previous
                        i += 1
                elif code == 17:
                    i += 3 + (yield from get_bits(3))
                    previous = 0
                elif code == 18:
                    i += 11 + (yield from get_bits(7))
                    previous = 0

            return result

        def yield_bytes(num_bytes):

            def to_yield():
                nonlocal num_bytes

                for chunk in reader_yield_bytes_up_to(num_bytes):
                    num_bytes -= len(chunk)
                    yield chunk

            while num_bytes:
                yield DeferredYielder(can_proceed=reader_has_byte, to_yield=via_cache(to_yield()), return_value=_none)

        def yield_from_cache_without_via(num_bytes):
            return DeferredYielder(can_proceed=_true, to_yield=from_cache(num_bytes, num_bytes), return_value=_none)

        def yield_from_cache(dist, length):
            return DeferredYielder(can_proceed=_true, to_yield=via_cache(from_cache(dist, length)), return_value=_none)

        _len = len
        b_final = 0

        # A circular cache storing the most recent cache_size bytes yielded in the stream, and
        # bytes that haven't quite yet been yielded, but will be
        cache = bytearray(cache_size)
        cache_end = 0
        cache_len = 0
        to_yield_in_cache = 0

        while not b_final:
            b_final = yield from get_bits(1)
            b_type = yield from get_bits(2)

            if b_type == 3:
                raise UnsupportedBlockType(b_type)

            if b_type == 0:
                b_len = int.from_bytes((yield from get_bytes(2)), byteorder='little')
                yield from get_bytes(2)
                yield from yield_bytes(b_len)
                continue

            if b_type == 1:
                literal_stop_or_length_codes = get_huffman_codes(literal_stop_or_length_code_lengths)
                backwards_dist_codes = get_huffman_codes(dist_code_lengths)
            else:
                num_literal_length_codes = (yield from get_bits(5)) + 257
                num_dist_codes = (yield from get_bits(5)) + 1
                num_length_codes = (yield from get_bits(4)) + 4

                code_length_code_lengths = (yield from get_code_length_code_lengths(num_length_codes)) + ((0,) * (19 - num_length_codes))
                code_length_code_lengths = tuple(
                    v for i, v in
                    sorted(enumerate(code_length_code_lengths), key=lambda x: code_lengths_alphabet[x[0]])
                )
                code_length_codes = get_huffman_codes(code_length_code_lengths)

                dynamic_code_lengths = yield from get_code_lengths(code_length_codes, num_literal_length_codes + num_dist_codes)
                dynamic_literal_code_lengths = dynamic_code_lengths[:num_literal_length_codes]
                dynamic_dist_code_lengths = dynamic_code_lengths[num_literal_length_codes:]

                literal_stop_or_length_codes = get_huffman_codes(dynamic_literal_code_lengths)
                backwards_dist_codes = get_huffman_codes(dynamic_dist_code_lengths)

            while True:
                literal_stop_or_length_code = yield from get_huffman_value(literal_stop_or_length_codes)
                if literal_stop_or_length_code < 256:
                    if to_yield_in_cache == cache_size:
                        yield yield_from_cache_without_via(to_yield_in_cache)
                        to_yield_in_cache = 0

                    cache[cache_end] = literal_stop_or_length_code
                    cache_end = (cache_end + 1) % cache_size
                    cache_len = (cache_len + 1) if (cache_len + 1) < cache_size else cache_size
                    to_yield_in_cache += 1
                elif literal_stop_or_length_code == 256:
                    break
                else:
                    length_extra_bits, length_diff = length_extra_bits_diffs[literal_stop_or_length_code - 257]
                    length_extra = int.from_bytes((yield from get_bits_as_bytes(length_extra_bits)), byteorder='little')

                    code = yield from get_huffman_value(backwards_dist_codes)
                    dist_extra_bits, dist_diff = dist_extra_bits_diffs[code]
                    dist_extra = int.from_bytes((yield from get_bits_as_bytes(dist_extra_bits)), byteorder='little')

                    if to_yield_in_cache:
                        yield yield_from_cache_without_via(to_yield_in_cache)
                        to_yield_in_cache = 0
                    yield yield_from_cache(dist=dist_extra + dist_diff, length=length_extra + length_diff)

        if to_yield_in_cache:
            yield yield_from_cache_without_via(to_yield_in_cache)
            to_yield_in_cache = 0

    def get_runner(append, inflater):
        is_done = False
        curr_deferred = None
        prev_deferred = None

        def _is_done():
            return is_done

        def _run(new_iterable):
            nonlocal is_done, curr_deferred, prev_deferred

            append(new_iterable)

            while True:
                if curr_deferred is None:
                    try:
                        curr_deferred = \
                            next(inflater) if prev_deferred is None else \
                            inflater.send(prev_deferred.return_value())
                    except StopIteration:
                        break
                if not curr_deferred.can_proceed():
                    return

                if curr_deferred.to_yield:
                    yield from curr_deferred.to_yield

                prev_deferred = curr_deferred
                curr_deferred = None

            is_done = True

        return _run, _is_done

    it_append, it_next = get_iterable_queue()
    reader_has_bit, reader_has_byte, reader_get_bit, reader_get_byte, reader_yield_bytes_up_to, reader_num_bytes_unconsumed = get_readers(it_next)
    get_bit, get_bits, get_bits_as_bytes, get_bytes = get_deferred_yielder_readers(reader_has_bit, reader_has_byte, reader_get_bit, reader_get_byte, reader_yield_bytes_up_to)
    inflater = inflate(get_bit, get_bits, get_bits_as_bytes, get_bytes, reader_yield_bytes_up_to)
    run, is_done = get_runner(it_append, inflater)

    return paginate(run, chunk_size), is_done, reader_num_bytes_unconsumed


class StreamInflateError(ValueError):
    pass


class UnsupportedBlockType(StreamInflateError):
    pass
