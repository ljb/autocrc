# AGENTS.md

Agent-facing notes for working in this repo. README has the user-facing overview.

## Environment

- Local venv lives at `./venv`. Activate before running anything: `source venv/bin/activate`.
- If `ruff` or `pytest` are missing, dev extras are not installed. Run `python -m pip install -e .[dev]`.
- Python 3.10+ (see `pyproject.toml`). Do not use 3.11-only features such as `StrEnum` — CI runs the
  test suite on 3.10 through 3.14.

## Commands

- Tests: `pytest -q` (config in `pyproject.toml` sets `pythonpath = ["src"]`).
- Lint: `ruff check`
- Format check: `ruff format --check`
- End-to-end: `python testbed/build.py && testbed/run-scenarios.sh` (needs `autocrc` installed,
  e.g. `pipx install --force .`). Slower to set up than pytest, so run it before a release rather
  than on every change.
- CI runs all of these (`.github/workflows/python-tests.yml`). Run them locally before declaring a
  task done.

## Project layout

- `src/autocrc/core.py` — the CRC-checking logic. Knows nothing about argparse, printing or exit codes.
- `src/autocrc/cli.py` — the `autocrc` entry point: argument parsing, output formatting, exit status.
- `tests/conftest.py` — `TempDirTestCase`, a base class that builds a throwaway directory tree, plus the
  payloads and their known CRC-sums.

## Conventions

- `core.py` must stay free of argparse and of output formatting. The CLI translates `Namespace` into
  `core.Options` and `core.CrcResult` into printed lines; that split is what makes the core testable.
- User-facing output goes through `print`, not logging.
- Tests are `unittest.TestCase` classes run by pytest, matching the sibling project `anidb-mv`.
- Tests exercise real files in a temp dir rather than mocking the filesystem. Only `sys.argv` is patched.
- Anything that depends on file permissions must be guarded with `@skipIf(os.geteuid() == 0, ...)` —
  root bypasses the permission bits and the test would fail.

## Output contract

The exact output format is a contract with users (it is modelled on pure-sfv) and is asserted in
`tests/test_cli.py::MainTest::test_output_format`. Do not casually change:

- `FILE_NAME_WIDTH = 77` — status text is right-aligned in the space left after the file name.
- `SEPARATOR_WIDTH = 80` — the `-` rule under each directory. It does not match `FILE_NAME_WIDTH`;
  that mismatch is inherited from the original implementation.
- The exit status: `different + missing * 2 + read_errors * 4`, `8` on an unhandled `OSError`, and
  `130` on Ctrl-C. A directory that could not be read during a recursive walk also sets the `4` bit,
  via `_exit_status(..., had_unreadable_dirs=True)` -- never let that path return 0.
- `Current directory:` headers are always absolute, and `walk_targets()` yields directories in
  sorted order. Both are deliberate: output should not depend on how a path was typed or on the
  order the filesystem hands entries back.
- `-q` skips the whole per-directory block when that directory is clean, so a fully successful
  quiet run prints nothing. The totals are still accumulated for the exit status.
- `-C/--directory` must chdir *before* `_split_paths()` runs, or relative positional arguments are
  resolved against the wrong directory and silently dropped.
- `_split_paths()` raises on a path that is neither a file nor a directory. Do not soften that back
  into a filter -- a silently dropped path made a mistyped argument look like a clean run.
- `walk_targets()` takes an `on_error` callback that is handed to `os.walk(onerror=...)`. Without it
  os.walk swallows unreadable directories, which made a partial scan look like a clean one.
