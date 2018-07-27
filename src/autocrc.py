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

"""
The core of autocrc. Performs the CRC-checks independent of what kind
of interface is used
"""
import mmap
import optparse
import os
import re
import zlib


class AutoParser(optparse.OptionParser):
    """Parse flags from the commandline"""

    def __init__(self):
        super().__init__(usage="%prog [OPTION]... [FILE]...",
                         version="%prog v0.4")

        self.add_option("-r", "--recursive", action="store_true",
                        help="CRC-check recursively")
        self.add_option("-i", "--ignore-case", action="store_true",
                        dest="case", help="ignore case for filenames parsed from sfv-files")
        self.add_option("-x", "--exchange", action="store_true",
                        help="interpret \\ as / for filenames parsed from sfv-files")
        self.add_option("-c", "--no-crc", action="store_false", dest="crc",
                        default=True, help="do not parse CRC-sums from filenames")
        self.add_option("-s", "--no-sfv", action="store_false", dest="sfv",
                        default=True, help="do not parse CRC-sums from sfv-files")
        self.add_option("-C", "--directory",
                        metavar="DIR", help="use DIR as the working directory")
        self.add_option("-L", "--follow", action="store_true",
                        help="follow symbolic directory links in recursive mode")

    def parse_args(self, _args=None, _values=None):
        flags, args = super().parse_args()
        file_names = [arg for arg in args if os.path.isfile(arg)]
        dir_names = [arg for arg in args if os.path.isdir(arg)] if args \
            else [os.curdir]
        return flags, file_names, dir_names


class Status:
    """Contains status information"""

    def __init__(self, nr_files=0):
        self.nr_missing = 0
        self.nr_different = 0
        self.nr_successful = 0
        self.nr_read_errors = 0
        self.nr_dirs = 0
        self.nr_files = nr_files

    def update(self, other):
        """Update status with data from another Status instance"""
        self.nr_missing += other.nr_missing
        self.nr_different += other.nr_different
        self.nr_successful += other.nr_successful
        self.nr_read_errors += other.nr_read_errors
        self.nr_dirs += 1
        self.nr_files += other.nr_files

    def everything_ok(self):
        """Returns true if no everything is ok"""
        return self.nr_read_errors == self.nr_different == self.nr_missing == 0


class Model:
    """An abstract model. Subclasses decides how the output is presented"""

    def __init__(self, flags, file_names=None, dir_names=None, block_size=8192):
        self.flags = flags
        self.file_names = file_names or []
        self.dir_names = dir_names or []
        self.block_size = block_size
        self.total_stat = Status()

    @staticmethod
    def parse(filename):
        """Returns the CRC parsed from the filename or None if no CRC is found"""
        crc = \
            re.match(r'.*?\[([a-fA-F0-9]{8})\].*?$', filename) or \
            re.match(r'.*?\(([a-fA-F0-9]{8})\).*?$', filename) or \
            re.match(r'.*?_([a-fA-F0-9]{8})_.*?$', filename)
        if crc:
            return crc.group(1).upper()

    def parse_line(self, line):
        """Parses a line from a sfv-file, returns a filename crc tuple"""
        match = re.match(r'([^;]+)\s([a-fA-F0-9]{8})\s*$', line)
        if match:
            # Make Windows directories into Unix directories
            if self.flags.exchange:
                return match.group(1).replace('\\', '/'), match.group(2).upper()
            else:
                return match.group(1), match.group(2).upper()

    def get_crcs(self, dirname, file_names):
        """Returns a dict with filename, crc pairs"""
        old_cwd = os.getcwd()
        os.chdir(dirname)

        files = [file_name for file_name in file_names if os.path.isfile(file_name)]
        sfv_files = [file_name for file_name in files if file_name.lower().endswith('.sfv')]
        crcs = {}

        # If case is to be ignore, build a dictionary with mappings from
        # filenames with lowercase to the filenames with the real case
        if not self.flags.case:
            no_case_files = {}

            for file_name in files:
                no_case_files[file_name.lower()] = file_name

        if sfv_files and self.flags.sfv:
            for sfv_file in sfv_files:
                with open(sfv_file, 'r', errors='replace') as file_:
                    for line in file_:
                        result = self.parse_line(line)
                        if result:
                            file_name, crc = result
                            if not self.flags.case and file_name.lower() in no_case_files:
                                crcs[no_case_files[file_name.lower()]] = crc
                            else:
                                crcs[file_name] = crc

        if self.flags.crc:
            for file in files:
                crc = self.parse(file)
                if crc:
                    crcs[file] = crc

        os.chdir(old_cwd)
        return crcs

    def crc32_of_file(self, filepath):
        """Returns the CRC of the file filepath"""

        with open(filepath, 'r+') as file_:
            with mmap.mmap(file_.fileno(), 0, access=mmap.ACCESS_READ) as map_:
                self.file_start(file_)

                current = 0
                while True:
                    buf = map_.read(self.block_size)
                    if not buf:
                        break
                    current = zlib.crc32(buf, current)
                    self.block_read()

                # Remove everything except the last 32 bits, including the leading 0x
                return hex(current & 0xFFFFFFFF)[2:].upper().zfill(8)

    def check_dir(self, dirname, file_names):
        """CRC-check the files in a directory"""
        crcs = self.get_crcs(dirname, file_names)

        if crcs:
            dir_stat = Status(len(crcs))
            self.directory_start(dirname, dir_stat)

            for file_name, crc in sorted(crcs.items()):
                try:
                    real_crc = self.crc32_of_file(os.path.join(dirname, file_name))
                except IOError as e:
                    if e.errno == 2:
                        dir_stat.nr_missing += 1
                        self.file_missing(file_name)
                    else:
                        dir_stat.nr_read_errors += 1
                        self.file_read_error(file_name)
                else:
                    if crc == real_crc:
                        dir_stat.nr_successful += 1
                        self.file_ok(file_name)
                    else:
                        dir_stat.nr_different += 1
                        self.file_different(file_name, crc, real_crc)

            self.total_stat.update(dir_stat)
            self.directory_end()

    # Hook methods, implemented by subclasses
    def file_ok(self, filename):
        """Called when a file was successfully CRC-checked"""
        pass

    def file_missing(self, filename):
        """Called when a file is missing"""
        pass

    def file_read_error(self, filename):
        """Called when a read error occurs on a file"""
        pass

    def file_different(self, filename, crc, real_crc):
        """Called when a CRC-mismatch occurs"""
        pass

    def directory_start(self, dirname, dir_stat):
        """Called when the CRC-checks on a directory is started"""
        pass

    def directory_end(self):
        """Called when the CRC-checks on a directory is complete"""
        pass

    def start(self):
        """Called when the CRC-checking starts"""
        pass

    def end(self):
        """Called when the CRC-checking is complete"""
        pass

    def file_start(self, file_):
        """Called when the CRC-checking of a file is started"""

    def block_read(self):
        """Called regularly in the loop where autocrc spends most of it's time."""
        pass

    def run(self):
        """Starts the CRC-checking"""

        self.start()

        if self.flags.directory:
            os.chdir(self.flags.dirname)

        # Mapping from a directory name to a list with the files that are
        # to be CRC-checked in that directory
        files_by_dir = {}
        for file_name in self.file_names:
            head, tail = os.path.split(file_name)
            head = os.path.abspath(head)
            if head not in files_by_dir:
                files_by_dir[head] = []
            files_by_dir[head].append(tail)

        for dirname, file_names in files_by_dir.items():
            self.check_dir(dirname, file_names)

        for dirname in self.dir_names:
            if self.flags.recursive:
                for root, dirs, files in os.walk(
                        dirname, followlinks=self.flags.follow):
                    self.check_dir(root, files)
            else:
                self.check_dir(dirname, os.listdir(dirname))

        self.end()
