# AutoCRC

autocrc uses 32-bit CRC-sums to verify the integrity of files. The CRC-sums are
parsed both from filenames and from sfv files.

autocrc can perform CRC-checks recursively. After it's done, it prints a
summary of the result.

### Prerequisites
Python 3.10 or later

### Installing
Install it with pip:
```
pip install autocrc
```

Or build and install from a checkout:
```
pip install .
```

### Examples of Usage
* To check the CRC of the files in the current directory: `autocrc`

* To check the CRC of the files recursively: `autocrc -r`

* To check the CRC of a specific file: `autocrc file[12345678].mkv`

* To check the CRCs specified in an sfv-file: `autocrc file.sfv`

* To check several files and directories at once: `autocrc file.sfv other[12345678].mkv some/dir`

### Exit Status
`autocrc` exits with a bitmask describing what went wrong:

| Value | Meaning |
| --- | --- |
| 0 | Everything OK |
| 1 | At least one CRC mismatch |
| 2 | At least one missing file |
| 4 | At least one read error |
| 8 | An unhandled I/O error occurred |
| 130 | Interrupted with Ctrl-C |

### Development
```
python -m venv venv
source venv/bin/activate
python -m pip install -e '.[dev]'

pytest -q
ruff check
ruff format --check
```

### Notes

The way the output is formatted is heavily influenced by pure-sfv.

`Current directory:` headers are always absolute, and directories are visited in
sorted order, so the output of a run does not depend on how the paths were typed
or on the order the filesystem returns them.

`-q` reports only the directories in which something went wrong. A run in which
everything checks out prints nothing at all.
