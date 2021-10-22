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

The following pattern can be used to find how many bytes of the last data chunk have not been consumed by the decompression.

```python
uncompressed_chunks, num_bytes_unconsumed = stream_inflate(compressed_chunks())
for uncompressed_chunk in uncompressed_chunks:
    print(uncompressed_chunk)

print(num_bytes_unconsumed())
```

This useful when there may be other data after the compressed part, such as in ZIP files.
