"""A commandline interface to autocrc"""
import os
import sys
from argparse import ArgumentParser, Namespace

from . import autocrc


def main() -> None:
    try:
        args, file_names, dir_names = parse_args()
        model = TextModel(args, file_names, dir_names)
        model.run()

    except OSError as e:
        print(f"autocrc: {e.filename}: {e.strerror}", file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt:
        pass


def parse_args() -> tuple[Namespace, list[str], list[str]]:
    parser = ArgumentParser()
    parser.add_argument("--version", action='version', version='%(prog)s v1.1')
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="CRC-check recursively")
    parser.add_argument("-i", "--ignore-case", action="store_false",
                        dest="case", help="ignore case for file_names parsed from sfv-files")
    parser.add_argument("-x", "--exchange", action="store_true",
                        help="interpret \\ as / for file_names parsed from sfv-files")
    parser.add_argument("-c", "--no-crc", action="store_false", dest="crc",
                        default=True, help="do not parse CRC-sums from file_names")
    parser.add_argument("-s", "--no-sfv", action="store_false", dest="sfv",
                        default=True, help="do not parse CRC-sums from sfv-files")
    parser.add_argument("-C", "--directory",
                        metavar="DIR", help="use DIR as the working directory")
    parser.add_argument("-L", "--follow", action="store_true",
                        help="follow symbolic directory links in recursive mode")

    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Only print error messages and summaries")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print the calculated CRC and the CRC it was compared against when mismatches occurs")
    parser.add_argument("files", nargs='?', default='.')

    args = parser.parse_args()
    file_names = [arg for arg in args.files if os.path.isfile(arg)]
    dir_names = [arg for arg in args.files if os.path.isdir(arg)] if args else [os.curdir]
    return args, file_names, dir_names


class TextModel(autocrc.Model):
    def __init__(self, args: Namespace, file_names: list[str],
                 dir_names: list[str]):
        super().__init__(args, file_names, dir_names)
        self.dir_stat: autocrc.StatusInformation | None = None

    def file_missing(self, file_name: str) -> None:
        """Print that a file is missing"""
        self.file_print(file_name, "No such file")

    def file_ok(self, file_name: str) -> None:
        """Print that a CRC-check was successful if quiet is false"""
        if not self.args.quiet:
            self.file_print(file_name, "OK")

    def file_different(self, file_name: str, crc: str, real_crc: str) -> None:
        """
        Print that a CRC-check failed. 
        If verbose is set then the CRC calculated and the CRC that it was 
        compared against is also printed
        """
        if self.args.verbose:
            self.file_print(file_name, f"{real_crc} != {crc}")
        else:
            self.file_print(file_name, "CRC mismatch")

    def file_read_error(self, file_name: str) -> None:
        """Print that a read error occurred"""
        self.file_print(file_name, "Read error")

    def directory_start(self, dir_name: str,
                        dir_stat: autocrc.StatusInformation) -> None:
        """Print that the CRC-checking of a directory has started"""
        self.dir_stat = dir_stat
        if dir_name == os.curdir:
            dir_name = os.path.abspath(dir_name)
        else:
            dir_name = os.path.normpath(dir_name)
        print("Current directory:", dir_name)

    def directory_end(self) -> None:
        """Print a summary of a directory."""
        print("-" * 80)

        if self.dir_stat.everything_ok():
            print("Everything OK")
        else:
            print("Errors occurred")
        s = self.dir_stat
        print(
            f"Tested {s.nr_files} files, Successful {s.nr_successful}, "
            f"Different {s.nr_different}, Missing {s.nr_missing}, "
            f"Read errors {s.nr_read_errors}\n")

    def end(self) -> None:
        """Print a total summary if more than one directory was scanned"""
        if self.total_stat.nr_files == 0:
            print("No CRC-sums found")

        elif self.total_stat.nr_dirs > 1:
            if self.total_stat.everything_ok():
                print("Everything OK")
            else:
                print("Errors Occurred")
            print("  Tested\t", self.total_stat.nr_files, "files")
            print("  Successful\t", self.total_stat.nr_successful, "files")
            print("  Different\t", self.total_stat.nr_different, "files")
            print("  Missing\t", self.total_stat.nr_missing, "files")
            print("  Read Errors\t", self.total_stat.nr_read_errors, "files")

        # Set the exit status to the value explained in usage()
        sys.exit((self.total_stat.nr_different > 0) +
                 (self.total_stat.nr_missing > 0) * 2 +
                 (self.total_stat.nr_read_errors > 0) * 4)

    @staticmethod
    def file_print(file_name: str, status: str) -> None:
        pad_len = max(0, 77 - len(file_name))
        norm_file_name = os.path.normpath(file_name)
        print(f"{norm_file_name} {status:>{pad_len}}")


if __name__ == '__main__':
    main()
