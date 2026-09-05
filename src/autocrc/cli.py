"""A commandline interface to autocrc."""

import os
import sys
from argparse import ArgumentParser, Namespace
from importlib.metadata import PackageNotFoundError, version

from .core import CrcResult, Options, Status, Summary, check_dir, walk_targets

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
            exchange=args.exchange,
            crc=args.crc,
            sfv=args.sfv,
            follow=args.follow,
        )

        total = Summary()
        for dir_path, dir_files in walk_targets(file_names, dir_names, options):
            results = check_dir(dir_path, dir_files, options)
            if not results:
                continue

            summary = Summary.from_results(results)
            total += summary

            # A quiet run only reports the directories that had something go wrong
            if args.quiet and summary.everything_ok:
                continue

            print("Current directory:", dir_path)
            for result in results:
                _print_result(result, quiet=args.quiet, verbose=args.verbose)
            _print_dir_summary(summary)

        _print_total_summary(total)
        sys.exit(_exit_status(total))

    except OSError as e:
        print(f"autocrc: {e.filename}: {e.strerror}", file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt:
        # 128 + SIGINT, so that an interrupted run is not mistaken for a successful one
        sys.exit(130)


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
        "--exchange",
        action="store_true",
        help="interpret \\ as / for file names parsed from sfv-files",
    )
    parser.add_argument(
        "-c",
        "--no-crc",
        action="store_false",
        dest="crc",
        help="do not parse CRC-sums from file names",
    )
    parser.add_argument(
        "-s",
        "--no-sfv",
        action="store_false",
        dest="sfv",
        help="do not parse CRC-sums from sfv-files",
    )
    parser.add_argument("-C", "--directory", metavar="DIR", help="use DIR as the working directory")
    parser.add_argument(
        "-L",
        "--follow",
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
    """Splits the given paths into a list of files and a list of directories."""
    file_names = [path for path in paths if os.path.isfile(path)]
    dir_names = [path for path in paths if os.path.isdir(path)]
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


def _exit_status(summary: Summary) -> int:
    return (summary.nr_different > 0) + (summary.nr_missing > 0) * 2 + (summary.nr_read_errors > 0) * 4


def _package_version() -> str:
    try:
        return version("autocrc")
    except PackageNotFoundError:
        return "unknown"


if __name__ == "__main__":
    main()
