# AutoCRC

autocrc uses 32-bit CRC-sums to verify the integrity of files. The CRC-sums are
parsed both from filenames and from sfv files.

autocrc can perform CRC-checks recursively. After it's done, it prints a
summary of the result.

### Prerequisites
Python 3

### Installing
Install it with pip:
```
pip install autocrc
```

Or build and install manually:
```
python setup.py build
python setup.py install
```

### Examples of Usage
* To check the CRC of the files in the current directory: `autocrc`

* To check the CRC of the files recursively: `autocrc -r`

* To check the CRC of a specific file: `autocrc file[12345678].mkv`

* To check the CRCs specified in an sfv-file: `autocrc file.sfv`

### TODO
* Improve the way --quite works
* More consequent treatment of paths in the console interface, at the moment
  it's not well defined when it prints absolute paths and when it prints
  relative paths
* Improve the part that parses CRC-sums from filenames, support for
  CRCs missing the leading zeroes.
* Fix bug: --ignore-case does not work for sfv-files with directories

### Notes

The way the output is formatted is heavily influenced by pure-sfv.
