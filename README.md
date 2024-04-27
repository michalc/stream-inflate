# stream-inflate [![PyPI package](https://img.shields.io/pypi/v/stream-inflate?label=PyPI%20package)](https://pypi.org/project/stream-inflate/) [![Test suite](https://img.shields.io/github/actions/workflow/status/michalc/stream-inflate/test.yml?label=Test%20suite)](https://github.com/michalc/stream-inflate/actions/workflows/test.yml) [![Code coverage](https://img.shields.io/codecov/c/github/michalc/stream-inflate?label=Code%20coverage)](https://app.codecov.io/gh/michalc/stream-inflate)

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

for uncompressed_chunk in stream_inflate()[0](compressed_chunks()):
    print(uncompressed_chunk)
```

To uncompress Deflate64, use the `stream_inflate64` function.

```python
for uncompressed_chunk in stream_inflate64()[0](compressed_chunks()):
    print(uncompressed_chunk)
```

For Deflate streams of unknown length where there may be other data _after_ the compressed part, the following pattern can be used to find how many bytes are not part of the compressed stream.

```python
uncompressed_chunks, is_done, num_bytes_unconsumed = stream_inflate()
it = iter(compressed_chunks())

while not is_done():
    chunk = next(it)
    for uncompressed in uncompressed_chunks((chunk,))
        print(uncompressed)

print(num_bytes_unconsumed())
```

This can be useful in certain ZIP files.
