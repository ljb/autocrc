"""The core of autocrc. Performs the CRC-checks independent of what kind of interface is used."""

import mmap
import os
import re
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum, auto

CRC_PATTERNS = (
    re.compile(r".*?\[([a-fA-F0-9]{8})\].*?$"),
    re.compile(r".*?\(([a-fA-F0-9]{8})\).*?$"),
    re.compile(r".*?_([a-fA-F0-9]{8})_.*?$"),
)
SFV_LINE_PATTERN = re.compile(r"([^;]+)\s([a-fA-F0-9]{8})\s*$")

BLOCK_SIZE = 8192
CRC_OF_EMPTY_FILE = "00000000"


class Status(Enum):
    """The outcome of CRC-checking a single file."""

    OK = auto()
    MISMATCH = auto()
    MISSING = auto()
    READ_ERROR = auto()


@dataclass(frozen=True)
class Options:
    """The knobs that affect how CRC-sums are collected and files are traversed."""

    recursive: bool = False
    case: bool = True
    windows_paths: bool = False
    crc: bool = True
    sfv: bool = True


@dataclass(frozen=True)
class CrcResult:
    """The result of CRC-checking one file. `actual` is None unless the file could be read."""

    name: str
    expected: str
    actual: str | None
    status: Status


@dataclass(frozen=True)
class Summary:
    """Aggregated counts over a set of CrcResults."""

    nr_files: int = 0
    nr_successful: int = 0
    nr_different: int = 0
    nr_missing: int = 0
    nr_read_errors: int = 0
    nr_dirs: int = 0

    @classmethod
    def from_results(cls, results: list[CrcResult]) -> "Summary":
        statuses = [result.status for result in results]
        return cls(
            nr_files=len(results),
            nr_successful=statuses.count(Status.OK),
            nr_different=statuses.count(Status.MISMATCH),
            nr_missing=statuses.count(Status.MISSING),
            nr_read_errors=statuses.count(Status.READ_ERROR),
            nr_dirs=1,
        )

    def __add__(self, other: "Summary") -> "Summary":
        return Summary(
            nr_files=self.nr_files + other.nr_files,
            nr_successful=self.nr_successful + other.nr_successful,
            nr_different=self.nr_different + other.nr_different,
            nr_missing=self.nr_missing + other.nr_missing,
            nr_read_errors=self.nr_read_errors + other.nr_read_errors,
            nr_dirs=self.nr_dirs + other.nr_dirs,
        )

    @property
    def everything_ok(self) -> bool:
        return self.nr_read_errors == self.nr_different == self.nr_missing == 0


def crc_from_filename(file_name: str) -> str | None:
    """Returns the CRC parsed from the file name, or None if no CRC is found."""
    for pattern in CRC_PATTERNS:
        if match := pattern.match(file_name):
            return match.group(1).upper()
    return None


def parse_sfv_line(line: str, windows_paths: bool = False) -> tuple[str, str] | None:
    """Parses a line from an sfv-file, returns a file name and CRC tuple."""
    if not (match := SFV_LINE_PATTERN.match(line)):
        return None

    file_name = match.group(1)
    if windows_paths:
        # Make Windows directories into Unix directories
        file_name = file_name.replace("\\", "/")
    return file_name, match.group(2).upper()


def crcs_in_dir(dir_path: str, file_names: list[str], options: Options) -> dict[str, str]:
    """Returns a dict with file name, CRC pairs for the files in dir_path."""
    files = [file_name for file_name in file_names if os.path.isfile(os.path.join(dir_path, file_name))]
    crcs = {}

    if options.sfv:
        sfv_files = [file_name for file_name in files if file_name.lower().endswith(".sfv")]
        for sfv_file in sfv_files:
            with open(os.path.join(dir_path, sfv_file), "r", errors="replace") as file_:
                for line in file_:
                    if result := parse_sfv_line(line, options.windows_paths):
                        file_name, crc = result
                        if not options.case:
                            file_name = _match_ignoring_case(dir_path, file_name)
                        crcs[file_name] = crc

    if options.crc:
        for file_name in files:
            if crc := crc_from_filename(file_name):
                crcs[file_name] = crc

    return crcs


def crc32_of_file(path: str, block_size: int = BLOCK_SIZE) -> str:
    """Returns the CRC of the file at path."""
    with open(path, "rb") as file_:
        if os.fstat(file_.fileno()).st_size == 0:
            return CRC_OF_EMPTY_FILE

        with mmap.mmap(file_.fileno(), 0, access=mmap.ACCESS_READ) as map_:
            current = 0
            while buf := map_.read(block_size):
                current = zlib.crc32(buf, current)

    # Remove everything except the last 32 bits, including the leading 0x
    return hex(current & 0xFFFFFFFF)[2:].upper().zfill(8)


def check_crcs(dir_path: str, crcs: dict[str, str]) -> Iterator[CrcResult]:
    """
    Yields one CrcResult per entry in crcs, in file name order.

    This is a generator so that a caller can report each file as it is checked.
    Hashing a directory of video files takes minutes, and a caller that waits for
    the whole list before printing anything is indistinguishable from one that hung.
    """
    for file_name, crc in sorted(crcs.items()):
        try:
            actual = crc32_of_file(os.path.join(dir_path, file_name))
        except FileNotFoundError:
            yield CrcResult(file_name, crc, None, Status.MISSING)
        except (OSError, ValueError):
            yield CrcResult(file_name, crc, None, Status.READ_ERROR)
        else:
            status = Status.OK if crc == actual else Status.MISMATCH
            yield CrcResult(file_name, crc, actual, status)


def check_dir(dir_path: str, file_names: list[str], options: Options) -> list[CrcResult]:
    """CRC-checks the files in a directory. Returns one CrcResult per file that had a CRC to check."""
    return list(check_crcs(dir_path, crcs_in_dir(dir_path, file_names, options)))


def walk_targets(
    file_names: list[str],
    dir_names: list[str],
    options: Options,
    on_error: Callable[[OSError], None] | None = None,
) -> Iterator[tuple[str, list[str]]]:
    """
    Yields (directory, file names) pairs for everything that should be CRC-checked.

    Directories are always absolute so that callers do not have to care whether the
    user named a path relatively, and are visited in sorted order so that the output
    of a run does not depend on the order the filesystem happens to hand them back.

    A directory that cannot be read during a recursive walk is passed to on_error and
    then skipped; os.walk would otherwise swallow it and let the run look complete.
    Directories named on the command line are not affected -- failing to read one of
    those raises, because the user asked for it by name.

    Symlinked directories are not descended into. A directory reachable by two paths
    would be checked twice and counted twice, and the summary is the whole point of
    the program. Naming such a directory on the command line still works: it is then
    the root of the walk rather than something found inside one.
    """
    # Individually named files are grouped by the directory they live in
    files_by_dir: dict[str, list[str]] = {}
    for file_name in file_names:
        head, tail = os.path.split(file_name)
        files_by_dir.setdefault(os.path.abspath(head), []).append(tail)

    yield from sorted(files_by_dir.items())

    for dir_name in dir_names:
        if options.recursive:
            for root, dirs, files in os.walk(dir_name, onerror=on_error):
                # Sorting in place makes os.walk descend in sorted order too
                dirs.sort()
                yield os.path.abspath(root), files
        else:
            yield os.path.abspath(dir_name), os.listdir(dir_name)


def _match_ignoring_case(dir_path: str, file_name: str) -> str:
    """
    Resolves file_name against the real entries under dir_path, ignoring case.

    Matching is done one path component at a time so that sfv-lines naming files in
    subdirectories are handled too. The file name is returned unchanged if no match is found.
    """
    resolved_parts = []
    current = dir_path

    for part in file_name.split("/"):
        try:
            entries = {entry.lower(): entry for entry in os.listdir(current)}
        except OSError:
            return file_name

        if (real_part := entries.get(part.lower())) is None:
            return file_name

        resolved_parts.append(real_part)
        current = os.path.join(current, real_part)

    return "/".join(resolved_parts)
