# stream-deflate

Uncompress DEFLATE streams in pure Python.

> Work in progress. This README serves as a rough design spec.


## Installation

```bash
pip install stream-deflate
```


## Usage

```python
from stream_deflate import stream_deflate
import httpx

def compressed_chunks():
    # Iterable that yields the bytes of a DEFLATE-compressed stream
    with httpx.stream('GET', 'https://www.example.com/my.txt') as r:
        yield from r.iter_raw(chunk_size=65536)

for uncompressed_chunk in stream_deflate(compressed_chunks()):
	print(uncompressed_chunk)
```
