#!/usr/bin/env python3

# Copyright 2007-2018 Jonas Bengtsson

# This file is part of autocrc.

# autocrc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# autocrc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A commandline interface to autocrc"""
import os
import sys
from argparse import ArgumentParser

from . import autocrc


def main():
    try:
        args, file_names, dir_names = parse_args()
        model = TextModel(args, file_names, dir_names)
        model.run()

    except OSError as e:
        print("autocrc: {}: {}".format(e.filename, e.strerror), file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt:
        pass


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--version", action='version', version='%(prog)s v1.0')
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
    def __init__(self, args, file_names, dir_names):
        super().__init__(args, file_names, dir_names)
        self.dir_stat = None

    def file_missing(self, file_name):
        """Print that a file is missing"""
        self.file_print(file_name, "No such file")

    def file_ok(self, file_name):
        """Print that a CRC-check was successful if quiet is false"""
        if not self.args.quiet:
            self.file_print(file_name, "OK")

    def file_different(self, file_name, crc, real_crc):
        """
        Print that a CRC-check failed. 
        If verbose is set then the CRC calculated and the CRC that it was 
        compared against is also printed
        """
        if self.args.verbose:
            self.file_print(file_name, real_crc + " != " + crc)
        else:
            self.file_print(file_name, "CRC mismatch")

    def file_read_error(self, file_name):
        """Print that a read error occurred"""
        self.file_print(file_name, "Read error")

    def directory_start(self, dir_name, dir_stat):
        """Print that the CRC-checking of a directory has started"""
        self.dir_stat = dir_stat
        if dir_name == os.curdir:
            dir_name = os.path.abspath(dir_name)
        else:
            dir_name = os.path.normpath(dir_name)
        print("Current directory:", dir_name)

    def directory_end(self):
        """Print a summary of a directory."""
        print("-" * 80)

        if self.dir_stat.everything_ok():
            print("Everything OK")
        else:
            print("Errors occurred")
        print(
            "Tested {0} files, Successful {1}, "
            "Different {2}, Missing {3}, Read errors {4}\n".format(
                self.dir_stat.nr_files, self.dir_stat.nr_successful,
                self.dir_stat.nr_different, self.dir_stat.nr_missing,
                self.dir_stat.nr_read_errors))

    def end(self):
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
    def file_print(file_name, status):
        pad_len = max(0, 77 - len(file_name))
        norm_file_name = os.path.normpath(file_name)
        print("{0} {1:>{2}}".format(norm_file_name, status, pad_len))


if __name__ == '__main__':
    main()
