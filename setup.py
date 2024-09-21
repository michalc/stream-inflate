import os
from setuptools import setup, Extension
from Cython.Build import cythonize

macros, compiler_directives = \
    ([('CYTHON_TRACE', '1')], {'linetrace': True}) if os.environ.get('STREAM_INFLATE_CODE_COVERAGE') == '1' else \
    ([], {})

print('Building...')
print('macros:', macros)
print('compiler_directives:', compiler_directives)

setup(
    ext_modules=cythonize([Extension(
        "stream_inflate",
        ["stream_inflate.py"],
        define_macros=macros,
    )], compiler_directives=compiler_directives),
    # Python 3.6 seems to need all of the below, even though they are in pyproject.toml
    name="stream-inflate",
    version="0.0.0.dev0",
    extras_require={
        'dev': [
            "coverage>=6.2",
            "pytest>=6.2.5",
            "pytest-cov>=3.0.0",
            "Cython>=3.0.0",
            "setuptools",
            "build",
        ]
    },
    py_modules=[
        'stream_inflate',
    ],
)
