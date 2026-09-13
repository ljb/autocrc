"""A commandline interface to autocrc."""

import errno
import os
import sys
from argparse import ArgumentParser, Namespace
from importlib.metadata import PackageNotFoundError, version

from .core import CrcResult, Options, Status, Summary, check_crcs, crcs_in_dir, walk_targets

FILE_NAME_WIDTH = 77
SEPARATOR_WIDTH = 80

STATUS_TEXT = {
    Status.OK: "OK",
    Status.MISSING: "No such file",
    Status.READ_ERROR: "Read error",
    Status.MISMATCH: "CRC mismatch",
}


def main() -> None:
    try:
        args = _parse_args()

        # Must happen before the paths are resolved, so that relative arguments are
        # interpreted against DIR rather than against the directory autocrc started in
        if args.directory:
            os.chdir(args.directory)

        file_names, dir_names = _split_paths(args.files)

        options = Options(
            recursive=args.recursive,
            case=args.case,
            windows_paths=args.windows_paths,
            crc=args.crc,
            sfv=args.sfv,
            follow_symlinks=args.follow_symlinks,
        )

        unreadable_dirs: list[OSError] = []

        def on_walk_error(error: OSError) -> None:
            """Reports a directory that could not be read, so the walk can carry on past it."""
            unreadable_dirs.append(error)
            print(f"autocrc: {error.filename}: {error.strerror}", file=sys.stderr)

        total = Summary()
        for dir_path, dir_files in walk_targets(file_names, dir_names, options, on_error=on_walk_error):
            total += _check_and_report(dir_path, dir_files, options, args)

        _print_total_summary(total)
        sys.exit(_exit_status(total, had_unreadable_dirs=bool(unreadable_dirs)))

    except OSError as e:
        print(f"autocrc: {e.filename}: {e.strerror}", file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt:
        # 128 + SIGINT, so that an interrupted run is not mistaken for a successful one
        sys.exit(130)


def _check_and_report(dir_path: str, dir_files: list[str], options: Options, args: Namespace) -> Summary:
    """CRC-checks one directory, reports it, and returns its summary."""
    crcs = crcs_in_dir(dir_path, dir_files, options)
    if not crcs:
        return Summary()

    # The header goes out before any hashing starts, and each file is reported as it
    # finishes. A directory of video files takes minutes, and a run that prints nothing
    # until it is done looks like it has hung.
    streaming = not args.quiet
    if streaming:
        print("Current directory:", dir_path)

    results = []
    for result in check_crcs(dir_path, crcs):
        results.append(result)
        if streaming:
            _print_result(result, quiet=False, verbose=args.verbose)

    summary = Summary.from_results(results)

    # Quiet mode cannot stream: whether to report the directory at all is only known
    # once every file in it has been checked.
    if not streaming:
        if summary.everything_ok:
            return summary
        print("Current directory:", dir_path)
        for result in results:
            _print_result(result, quiet=True, verbose=args.verbose)

    _print_dir_summary(summary)
    return summary


def _parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("--version", action="version", version=f"%(prog)s v{_package_version()}")
    parser.add_argument("-r", "--recursive", action="store_true", help="CRC-check recursively")
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_false",
        dest="case",
        help="ignore case for file names parsed from sfv-files",
    )
    parser.add_argument(
        "-x",
        "--windows-paths",
        action="store_true",
        help="interpret \\ as / for file names parsed from sfv-files",
    )
    parser.add_argument(
        "--no-crc",
        action="store_false",
        dest="crc",
        help="do not parse CRC-sums from file names",
    )
    parser.add_argument(
        "--no-sfv",
        action="store_false",
        dest="sfv",
        help="do not parse CRC-sums from sfv-files",
    )
    parser.add_argument("-C", "--directory", metavar="DIR", help="use DIR as the working directory")
    parser.add_argument(
        "-L",
        "--follow-symlinks",
        action="store_true",
        help="follow symbolic directory links in recursive mode",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only report directories in which something went wrong",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print the calculated CRC and the CRC it was compared against when mismatches occur",
    )
    parser.add_argument("files", nargs="*", default=[os.curdir], help="the files and directories to CRC-check")

    args = parser.parse_args()
    if not args.files:
        args.files = [os.curdir]
    return args


def _split_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """
    Splits the given paths into a list of files and a list of directories.

    Anything that is neither raises, so that a mistyped path is reported instead of
    being quietly dropped -- which used to make a typo look like a successful run.
    """
    file_names, dir_names = [], []

    for path in paths:
        if os.path.isfile(path):
            file_names.append(path)
        elif os.path.isdir(path):
            dir_names.append(path)
        elif not os.path.exists(path):
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)
        else:
            raise OSError(errno.EINVAL, "Not a file or directory", path)

    return file_names, dir_names


def _print_result(result: CrcResult, quiet: bool = False, verbose: bool = False) -> None:
    if result.status is Status.OK and quiet:
        return

    if result.status is Status.MISMATCH and verbose:
        status = f"{result.actual} != {result.expected}"
    else:
        status = STATUS_TEXT[result.status]

    _print_file(result.name, status)


def _print_dir_summary(summary: Summary) -> None:
    print("-" * SEPARATOR_WIDTH)
    print("Everything OK" if summary.everything_ok else "Errors occurred")
    print(
        f"Tested {summary.nr_files} files, Successful {summary.nr_successful}, "
        f"Different {summary.nr_different}, Missing {summary.nr_missing}, "
        f"Read errors {summary.nr_read_errors}\n"
    )


def _print_total_summary(summary: Summary) -> None:
    """Prints a total summary if more than one directory was scanned."""
    if summary.nr_files == 0:
        print("No CRC-sums found")
    elif summary.nr_dirs > 1:
        print("Everything OK" if summary.everything_ok else "Errors Occurred")
        print("  Tested\t", summary.nr_files, "files")
        print("  Successful\t", summary.nr_successful, "files")
        print("  Different\t", summary.nr_different, "files")
        print("  Missing\t", summary.nr_missing, "files")
        print("  Read Errors\t", summary.nr_read_errors, "files")


def _print_file(file_name: str, status: str) -> None:
    pad_len = max(0, FILE_NAME_WIDTH - len(file_name))
    print(f"{os.path.normpath(file_name)} {status:>{pad_len}}")


def _exit_status(summary: Summary, had_unreadable_dirs: bool = False) -> int:
    return (
        (summary.nr_different > 0)
        + (summary.nr_missing > 0) * 2
        + (summary.nr_read_errors > 0 or had_unreadable_dirs) * 4
    )


def _package_version() -> str:
    try:
        return version("autocrc")
    except PackageNotFoundError:
        return "unknown"


if __name__ == "__main__":
    main()
