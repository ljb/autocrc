# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09-13

The previous release on PyPI is 1.0. A 1.1 was tagged in the repository but never
published, which is why this release jumps straight to 2.0.0.

### Upgrading from 1.0

- Python 3.10 or later is now required. `pip install` fails on older interpreters.
- Replace `-c` with `--no-crc` and `-s` with `--no-sfv`.
- Replace `--exchange` with `--windows-paths`.
- `-L`/`--follow` is gone. Name a symlinked directory on the command line instead
  of relying on a recursive walk to find it.
- Scripts that read autocrc's output need a second look: `-q` no longer prints
  anything for directories where everything is fine, and directory headers are now
  always absolute.
- Scripts that check the exit status need a second look too: a mistyped path and an
  interrupted run used to exit 0 and no longer do.
- Anything importing `autocrc.autocrc` or `autocrc.text` must be rewritten against
  `autocrc.core` and `autocrc.cli`.

### Removed

- **The `-c` and `-s` short options.** Both were negations wearing a positive
  name, and `-c` sat one shift key away from the unrelated `-C/--directory`. The
  long forms `--no-crc` and `--no-sfv` are kept.
- **The `--exchange` option**, renamed to `--windows-paths`.
- **The `-L`/`--follow` option.** A directory reachable through two paths was
  checked and counted twice, so a recursive run's summary -- the thing autocrc
  exists to produce -- reported more files than the tree contains. A link pointing
  at its own ancestor was worse: autocrc re-read the same files 41 times before the
  kernel's symlink limit ended the walk, silently and with exit 0. Symlinked
  directories are no longer descended into. Naming one on the command line still
  works, because it is then the root of the walk.
- **Support for Python versions before 3.10.** `pip install` now fails on older
  interpreters rather than installing something that cannot run.
- The `Model`, `TextModel` and `StatusInformation` classes. The hook-method
  architecture was a leftover from GUI support removed years earlier.

### Changed

- **Exit status on a path that does not exist is now 8 instead of 0.** Arguments
  that were neither a file nor a directory used to be dropped silently, so a typo
  was indistinguishable from a clean run.
- **Exit status on Ctrl-C is now 130 instead of 0.** An interrupted run no longer
  looks successful to the caller.
- **A directory that cannot be read during a recursive walk is now reported** on
  stderr and sets the read-error bit in the exit status. `os.walk` swallowed the
  error, so a partial scan reported "No CRC-sums found" and exited 0.
- **`-q/--quiet` now skips clean directories entirely.** It used to hide only the
  per-file `OK` lines, leaving six lines of header and summary per directory. A run
  in which everything checks out now prints nothing at all.
- **`Current directory:` headers are always absolute.** They used to be absolute for
  a named file or for `.`, but relative for any other directory, so a single
  `autocrc -r .` mixed both forms.
- **Directories are visited in sorted order**, so the output of a recursive run does
  not depend on the order the filesystem returns entries.
- The package moved to a `src/` layout, and the modules were renamed:
  `autocrc.autocrc` is now `autocrc.core` and `autocrc.text` is now `autocrc.cli`.
  The console script entry point is `autocrc.cli:main`.
- The public API is functions returning frozen dataclasses: `Options`, `CrcResult`,
  `Summary` and `Status`. `core` no longer imports argparse or formats output.
- `--version` reads the version from the package metadata instead of a hardcoded
  string that had already drifted out of sync once.

### Fixed

- **`autocrc FILE` did nothing.** The positional argument was declared with
  `nargs='?'`, so it arrived as a string and was iterated character by character.
  Every explicit argument was discarded and the run reported "No CRC-sums found"
  and exited 0. Only the bare `autocrc` worked, by accident of its `'.'` default.
  Present in 1.0.
- **Read-only files were counted as read errors.** Files were opened with `'r+'`,
  which asks for write permission. They are now opened `'rb'`.
- **Empty files crashed the run** with `ValueError: cannot mmap an empty file`.
  They now hash to `00000000`.
- **`-C DIR` combined with a relative argument found nothing.** The paths were
  resolved before the working directory was changed, so `autocrc -C target sub`
  reported "No CRC-sums found" and exited 0.
- **`--ignore-case` did not match sfv lines naming files in subdirectories.**
  Matching only considered the basename; it is now done per path component.
- The working directory is no longer changed while collecting CRC-sums, which used
  to leak if an exception was raised mid-scan.
- The sdist shipped `tests/test_*.py` without `tests/conftest.py`, so the test suite
  could not be run from it.

### Added

- A test suite of 66 tests, including a regression test for every bug listed above.
- `testbed/`, a set of scenarios run against the installed command -- real
  permission bits, symlinks, a fifo, Windows-style sfv paths -- checked in CI so the
  behaviour they document cannot quietly drift.
- `MANIFEST.in`, so the sdist ships a test suite that actually runs.
- ruff for linting and formatting, pytest configuration, and a `dev` extra that
  installs both.
- CI running the tests on Python 3.10 through 3.14 plus a lint job, and a workflow
  that publishes to PyPI via trusted publishing on release.
- The exit status is documented in the README.
- `AGENTS.md` with project notes, including the parts of the output that are a
  contract with users.

## [1.0] - 2018-08-12

First release under this version scheme. See the git history for earlier changes.

[2.0.0]: https://github.com/ljb/autocrc/compare/v1.0...v2.0.0
[1.0]: https://github.com/ljb/autocrc/releases/tag/v1.0
