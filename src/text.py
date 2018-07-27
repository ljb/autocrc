#!/usr/bin/env python3

# Copyright 2007-2008 Jonas Bengtsson

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
import optparse
import os
import sys

from . import autocrc


def main():
    """The main function"""
    try:
        flags, file_names, dir_names = parse_args()
        model = TextModel(flags, file_names, dir_names)
        model.run()

    except OSError as e:
        print("autocrc: {}: {}".format(e.filename, e.strerror), file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt:
        pass


def parse_args():
    parser = optparse.OptionParser(usage="%pro [OPTION]... [FILE]...", version="%prog v0.4")

    parser.add_option("-r", "--recursive", action="store_true",
                      help="CRC-check recursively")
    parser.add_option("-i", "--ignore-case", action="store_true",
                      dest="case", help="ignore case for filenames parsed from sfv-files")
    parser.add_option("-x", "--exchange", action="store_true",
                      help="interpret \\ as / for filenames parsed from sfv-files")
    parser.add_option("-c", "--no-crc", action="store_false", dest="crc",
                      default=True, help="do not parse CRC-sums from filenames")
    parser.add_option("-s", "--no-sfv", action="store_false", dest="sfv",
                      default=True, help="do not parse CRC-sums from sfv-files")
    parser.add_option("-C", "--directory",
                      metavar="DIR", help="use DIR as the working directory")
    parser.add_option("-L", "--follow", action="store_true",
                      help="follow symbolic directory links in recursive mode")

    parser.add_option("-q", "--quiet", action="store_true",
                      help="Only print error messages and summaries")
    parser.add_option("-v", "--verbose", action="store_true",
                      help="Print the calculated CRC and the CRC it was compared against when mismatches occurs")

    flags, args = parser.parse_args()
    file_names = [arg for arg in args if os.path.isfile(arg)]
    dir_names = [arg for arg in args if os.path.isdir(arg)] if args else [os.curdir]
    return flags, file_names, dir_names


class TextModel(autocrc.Model):
    def __init__(self, flags, file_names, dir_names):
        super().__init__(flags, file_names, dir_names)
        self.dir_stat = None

    def file_missing(self, filename):
        """Print that a file is missing"""
        self.file_print(filename, "No such file")

    def file_ok(self, filename):
        """Print that a CRC-check was successful if quiet is false"""
        if not self.flags.quiet:
            self.file_print(filename, "OK")

    def file_different(self, filename, crc, real_crc):
        """
        Print that a CRC-check failed. 
        If verbose is set then the CRC calculated and the CRC that it was 
        compared against is also printed
        """
        if self.flags.verbose:
            self.file_print(filename, real_crc + " != " + crc)
        else:
            self.file_print(filename, "CRC mismatch")

    def file_read_error(self, filename):
        """Print that a read error occurred"""
        self.file_print(filename, "Read error")

    def directory_start(self, dirname, dir_stat):
        """Print that the CRC-checking of a directory has started"""
        self.dir_stat = dir_stat
        if dirname == os.curdir:
            dirname = os.path.abspath(dirname)
        else:
            dirname = os.path.normpath(dirname)
        print("Current directory:", dirname)

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
    def file_print(filename, status):
        pad_len = max(0, 77 - len(filename))
        norm_file_name = os.path.normpath(filename)
        print("{0} {1:>{2}}".format(norm_file_name, status, pad_len))


if __name__ == '__main__':
    main()
