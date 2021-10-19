# stream-inflate [![CircleCI](https://circleci.com/gh/michalc/stream-inflate.svg?style=shield)](https://circleci.com/gh/michalc/stream-inflate) [![Test Coverage](https://api.codeclimate.com/v1/badges/1131e6ac6efb36647a9b/test_coverage)](https://codeclimate.com/github/michalc/stream-inflate/test_coverage)

Uncompress Deflate and Deflate64 streams in pure Python.


## Installation

```bash
pip install stream-inflate
```


## Usage

To uncompress Deflate, use the `stream_inflate` function.

```python
from stream_inflate import stream_inflate
import httpx

def compressed_chunks():
    # Iterable that yields the bytes of a DEFLATE-compressed stream
    with httpx.stream('GET', 'https://www.example.com/my.txt') as r:
        yield from r.iter_raw(chunk_size=65536)

for uncompressed_chunk in stream_inflate(compressed_chunks())[0]:
    print(uncompressed_chunk)
```

To uncompress Deflate64, use the `stream_inflate64` function.

```python
for uncompressed_chunk in stream_inflate64(compressed_chunks())[0]:
    print(uncompressed_chunk)
```

If you have a stream that has other data after the compressed part, but exactly where isn't known in advance, the following pattern can be used to retrieve the index of the end of the compressed stream, relative to the last data chunk consumed.

```python
uncompressed_chunks, get_end_index = stream_inflate(compressed_chunks())
for uncompressed_chunk in uncompressed_chunks:
    print(uncompressed_chunk)

print(get_end_index())
```

This is possible since Deflate and Deflate64-encoded streams indicate their end.
