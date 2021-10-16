import setuptools


def long_description():
    with open('README.md', 'r') as file:
        return file.read()


setuptools.setup(
    name='stream-deflate',
    version='0.0.0',
    author='Michal Charemza',
    author_email='michal@charemza.name',
    description='Uncompress DEFLATE streams in pure Python',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/michalc/stream-deflate',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Topic :: System :: Archiving :: Compression',
    ],
    python_requires='>=3.5.0',
    py_modules=[
        'stream_deflate',
    ],
)
