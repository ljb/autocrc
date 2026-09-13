#!/usr/bin/env python3
"""
Builds (or rebuilds) the autocrc testbed.

    ./build.py           rebuild everything
    ./build.py --clean   remove everything and stop

Every CRC that is meant to match is computed from the actual file contents, so a
scenario that says OK really is OK. Scenarios that are meant to fail use the
deliberately wrong sum DEADBEEF.
"""

import os
import shutil
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Everything generated lives under one directory, so .gitignore and the linter
# exclusions are a single path rather than a list of scenario names.
SCENARIOS = ROOT / "scenarios"
WRONG_CRC = "DEADBEEF"
# Big enough that per-file output can be watched arriving. CI has nothing to watch,
# so it can shrink this: AUTOCRC_TESTBED_LARGE_FILE_SIZE=65536 ./build.py
LARGE_FILE_SIZE = int(os.environ.get("AUTOCRC_TESTBED_LARGE_FILE_SIZE", 64 * 1024 * 1024))


def crc(data: bytes) -> str:
    return format(zlib.crc32(data) & 0xFFFFFFFF, "08X")


def write(path: Path, data: bytes = b"") -> str:
    """Creates a file and returns the CRC of its contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return crc(data)


def clean() -> None:
    """Removes the generated scenarios. Unreadable directories need their mode back first."""
    if not SCENARIOS.exists():
        return
    for dirpath, dirnames, _ in os.walk(SCENARIOS, topdown=False):
        for name in dirnames:
            with suppress_oserror():
                os.chmod(os.path.join(dirpath, name), 0o755)
    shutil.rmtree(SCENARIOS, ignore_errors=True)


class suppress_oserror:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        return exc_type is not None and issubclass(exc_type, OSError)


def build_filename_crcs() -> None:
    """The three delimiters autocrc understands, plus things it should ignore."""
    d = SCENARIOS / "01-filename-crcs"
    payload = b"square brackets\n"
    write(d / f"ok-brackets [{crc(payload)}].bin", payload)

    payload = b"parentheses\n"
    write(d / f"ok-parens ({crc(payload)}).bin", payload)

    payload = b"underscores\n"
    write(d / f"ok_underscores_{crc(payload)}_.bin", payload)

    payload = b"lowercase hex still matches\n"
    write(d / f"ok-lowercase [{crc(payload).lower()}].bin", payload)

    write(d / f"BAD-mismatch [{WRONG_CRC}].bin", b"this does not hash to DEADBEEF\n")

    # Nothing here looks like a CRC, so autocrc never touches these
    write(d / "ignored-no-crc.bin", b"no sum in the name\n")
    write(d / "ignored-too-short [1F2E3D4].bin", b"seven hex digits\n")
    write(d / "ignored-not-hex [ZZZZZZZZ].bin", b"not hexadecimal\n")


def build_sfv_basic() -> None:
    d = SCENARIOS / "02-sfv-basic"
    lines = ["; a comment line, ignored", ";", "; blank-ish lines below are skipped too", ""]

    payload = b"listed in the sfv\n"
    lines.append(f"ok-from-sfv.bin {write(d / 'ok-from-sfv.bin', payload)}")
    write(d / "BAD-from-sfv.bin", b"contents do not match\n")
    lines.append(f"BAD-from-sfv.bin {WRONG_CRC}")
    lines.append(f"MISSING-never-created.bin {WRONG_CRC}")

    payload = b"in a subdirectory\n"
    lines.append(f"subdir/ok-nested.bin {write(d / 'subdir' / 'ok-nested.bin', payload)}")

    (d / "check.sfv").write_text("\n".join(lines) + "\n")


def build_sfv_windows_paths() -> None:
    """Backslash separators, which need -x/--windows-paths."""
    d = SCENARIOS / "03-sfv-windows-paths"
    payload = b"reached through a backslash path\n"
    digest = write(d / "Season 1" / "episode.bin", payload)
    (d / "windows.sfv").write_text(f"; needs -x to resolve\r\nSeason 1\\episode.bin {digest}\r\n")


def build_sfv_ignore_case() -> None:
    """Names whose case does not match the filesystem, which need -i/--ignore-case."""
    d = SCENARIOS / "04-sfv-ignore-case"
    flat = write(d / "MixedCase.bin", b"case differs in the sfv\n")
    nested = write(d / "SubDir" / "Nested.bin", b"case differs in both components\n")
    (d / "check.sfv").write_text(f"mixedcase.BIN {flat}\nsubdir/nested.BIN {nested}\n")


def build_permissions() -> None:
    d = SCENARIOS / "05-permissions"
    payload = b"readable but not writable\n"
    write(d / f"ok-read-only [{crc(payload)}].bin", payload)
    os.chmod(d / f"ok-read-only [{crc(payload)}].bin", 0o444)

    payload = b"cannot be opened at all\n"
    unreadable = d / f"BAD-unreadable [{crc(payload)}].bin"
    write(unreadable, payload)
    os.chmod(unreadable, 0o000)

    # Only reached by -r, and only to be refused
    locked = d / "locked-dir"
    payload = b"nobody can list the directory this is in\n"
    write(locked / f"hidden [{crc(payload)}].bin", payload)
    os.chmod(locked, 0o000)


def build_empty_and_missing() -> None:
    d = SCENARIOS / "06-empty-and-missing"
    write(d / "ok-empty [00000000].bin", b"")
    write(d / f"BAD-empty-wrong-sum [{WRONG_CRC}].bin", b"")
    (d / "missing.sfv").write_text(f"gone.bin {WRONG_CRC}\nalso-gone.bin {WRONG_CRC}\n")


def build_symlinks() -> None:
    d = SCENARIOS / "07-symlinks"
    d.mkdir(parents=True, exist_ok=True)

    payload = b"the real file behind the link\n"
    digest = write(d / "target.bin", payload)

    # The CRC is on the link's own name; isfile() follows it, so this is checked
    (d / f"ok-link [{digest}].bin").symlink_to("target.bin")

    # isfile() is False for a broken link, so autocrc skips it without a word
    (d / f"skipped-broken-link [{digest}].bin").symlink_to("nowhere.bin")

    payload = b"inside a real subdirectory\n"
    write(d / "real-subdir" / f"ok-nested [{crc(payload)}].bin", payload)
    # Never descended into by -r; naming it on the command line still works
    (d / "linked-subdir").symlink_to("real-subdir", target_is_directory=True)


def build_recursive() -> None:
    """A tree for -r, also showing that directories are visited in sorted order."""
    d = SCENARIOS / "08-recursive"
    for name in ("charlie", "alpha", "bravo"):
        payload = f"inside {name}\n".encode()
        write(d / name / f"ok [{crc(payload)}].bin", payload)
    write(d / "no-crcs-here" / "nothing.bin", b"this directory is never reported\n")
    payload = b"at the top of the tree\n"
    write(d / f"ok-top [{crc(payload)}].bin", payload)


def build_exit_codes() -> None:
    """One directory per exit-status bit, so each can be checked on its own."""
    base = SCENARIOS / "09-exit-codes"

    write(base / "status-1-mismatch" / f"BAD [{WRONG_CRC}].bin", b"wrong sum\n")

    (base / "status-2-missing").mkdir(parents=True, exist_ok=True)
    (base / "status-2-missing" / "check.sfv").write_text(f"gone.bin {WRONG_CRC}\n")

    payload = b"unreadable\n"
    unreadable = base / "status-4-read-error" / f"BAD [{crc(payload)}].bin"
    write(unreadable, payload)
    os.chmod(unreadable, 0o000)

    d = base / "status-7-everything"
    write(d / f"BAD-mismatch [{WRONG_CRC}].bin", b"wrong sum\n")
    payload = b"unreadable\n"
    write(d / f"BAD-unreadable [{crc(payload)}].bin", payload)
    os.chmod(d / f"BAD-unreadable [{crc(payload)}].bin", 0o000)
    (d / "check.sfv").write_text(f"gone.bin {WRONG_CRC}\n")


def build_large_files() -> None:
    """Big enough that the per-file output can be watched arriving."""
    d = SCENARIOS / "10-large-files"
    d.mkdir(parents=True, exist_ok=True)
    for name in ("first", "second", "third"):
        data = os.urandom(LARGE_FILE_SIZE)
        write(d / f"{name} [{crc(data)}].bin", data)


def build_odd_arguments() -> None:
    """Things that are not ordinary files, for the argument-validation paths."""
    d = SCENARIOS / "11-odd-arguments"
    d.mkdir(parents=True, exist_ok=True)
    fifo = d / "a-fifo"
    if not fifo.exists():
        os.mkfifo(fifo)
    payload = b"an ordinary file to contrast with\n"
    write(d / f"ok-ordinary [{crc(payload)}].bin", payload)


def main() -> None:
    if "--clean" in sys.argv:
        clean()
        print(f"Removed {SCENARIOS}")
        return

    clean()
    for builder in (
        build_filename_crcs,
        build_sfv_basic,
        build_sfv_windows_paths,
        build_sfv_ignore_case,
        build_permissions,
        build_empty_and_missing,
        build_symlinks,
        build_recursive,
        build_exit_codes,
        build_large_files,
        build_odd_arguments,
    ):
        builder()
        print(f"  {builder.__name__.removeprefix('build_')}")

    print(f"\nTestbed ready under {SCENARIOS}")
    print("Read README.md, or run ./run-scenarios.sh for a pass over everything.")


if __name__ == "__main__":
    main()
