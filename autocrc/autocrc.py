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

"""
The core of autocrc. Performs the CRC-checks independent of what kind
of interface is used
"""
import io
import mmap
import os
import re
import zlib
from argparse import Namespace
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class StatusInformation:
    nr_files: int = 0
    nr_missing: int = 0
    nr_different: int = 0
    nr_successful: int = 0
    nr_read_errors: int = 0
    nr_dirs: int = 0

    def update(self, other: "StatusInformation") -> None:
        """Update status with data from another Status instance"""
        self.nr_missing += other.nr_missing
        self.nr_different += other.nr_different
        self.nr_successful += other.nr_successful
        self.nr_read_errors += other.nr_read_errors
        self.nr_dirs += 1
        self.nr_files += other.nr_files

    def everything_ok(self) -> bool:
        """Returns true if everything is ok"""
        return self.nr_read_errors == self.nr_different == self.nr_missing == 0


class Model:
    """An abstract model. Subclasses decides how the output is presented"""

    def __init__(self, flags: Namespace, file_names: list[str] | None = None,
                 dir_names: list[str] | None = None, block_size: int = 8192):
        self.args = flags
        self.file_names = file_names or []
        self.dir_names = dir_names or []
        self.block_size = block_size
        self.total_stat = StatusInformation()

    @staticmethod
    def parse(file_name: str) -> str | None:
        """Returns the CRC parsed from the file_name or None if no CRC is found"""
        if crc := (
            re.match(r'.*?\[([a-fA-F0-9]{8})\].*?$', file_name) or
            re.match(r'.*?\(([a-fA-F0-9]{8})\).*?$', file_name) or
            re.match(r'.*?_([a-fA-F0-9]{8})_.*?$', file_name)
        ):
            return crc.group(1).upper()

    def parse_line(self, line: str) -> tuple[str, str] | None:
        """Parses a line from a sfv-file, returns a file name crc tuple"""
        if match := re.match(r'([^;]+)\s([a-fA-F0-9]{8})\s*$', line):
            # Make Windows directories into Unix directories
            if self.args.exchange:
                return match.group(1).replace('\\', '/'), match.group(2).upper()
            else:
                return match.group(1), match.group(2).upper()

    def get_crcs(self, dir_name: str, file_names: list[str]) -> dict[str, str]:
        """Returns a dict with file_name, crc pairs"""
        old_cwd = os.getcwd()
        os.chdir(dir_name)

        files = [file_name for file_name in file_names if os.path.isfile(file_name)]
        sfv_files = [file_name for file_name in files if file_name.lower().endswith('.sfv')]
        crcs = {}

        # If case is to be ignore, build a dictionary with mappings from
        # file_names with lowercase to the file names with the real case
        no_case_files = {file_name.lower(): file_name for file_name in files}

        if sfv_files and self.args.sfv:
            for sfv_file in sfv_files:
                with open(sfv_file, 'r', errors='replace') as file_:
                    for line in file_:
                        if result := self.parse_line(line):
                            file_name, crc = result
                            if not self.args.case and file_name.lower() in no_case_files:
                                crcs[no_case_files[file_name.lower()]] = crc
                            else:
                                crcs[file_name] = crc

        if self.args.crc:
            for file in files:
                if crc := self.parse(file):
                    crcs[file] = crc

        os.chdir(old_cwd)
        return crcs

    def crc32_of_file(self, file_path: str) -> str:
        """Returns the CRC of the file filepath"""

        with (
            open(file_path, 'r+') as file_,
            mmap.mmap(file_.fileno(), 0, access=mmap.ACCESS_READ) as map_,
        ):
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

    def check_dir(self, dir_name: str, file_names: list[str]) -> None:
        """CRC-check the files in a directory"""
        crcs = self.get_crcs(dir_name, file_names)

        if crcs:
            dir_stat = StatusInformation(len(crcs))
            self.directory_start(dir_name, dir_stat)

            for file_name, crc in sorted(crcs.items()):
                try:
                    real_crc = self.crc32_of_file(os.path.join(dir_name, file_name))
                except OSError as e:
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
    def file_ok(self, file_name: str) -> None:
        """Called when a file was successfully CRC-checked"""
        pass

    def file_missing(self, file_name: str) -> None:
        """Called when a file is missing"""
        pass

    def file_read_error(self, file_name: str) -> None:
        """Called when a read error occurs on a file"""
        pass

    def file_different(self, file_name: str, crc: str, real_crc: str) -> None:
        """Called when a CRC-mismatch occurs"""
        pass

    def directory_start(self, dir_name: str, dir_stat: StatusInformation) -> None:
        """Called when the CRC-checks on a directory is started"""
        pass

    def directory_end(self) -> None:
        """Called when the CRC-checks on a directory is complete"""
        pass

    def start(self) -> None:
        """Called when the CRC-checking starts"""
        pass

    def end(self) -> None:
        """Called when the CRC-checking is complete"""
        pass

    def file_start(self, file_: io.TextIOWrapper) -> None:
        """Called when the CRC-checking of a file is started"""
        pass

    def block_read(self) -> None:
        """Called regularly in the loop where autocrc spends most of it's time."""
        pass

    def run(self) -> None:
        """Starts the CRC-checking"""

        self.start()

        if self.args.directory:
            os.chdir(self.args.directory)

        # Mapping from a directory name to a list with the files that are
        # to be CRC-checked in that directory
        files_by_dir: defaultdict[str, list[str]] = defaultdict(list)
        for file_name in self.file_names:
            head, tail = os.path.split(file_name)
            files_by_dir[os.path.abspath(head)].append(tail)

        for dir_name, file_names in files_by_dir.items():
            self.check_dir(dir_name, file_names)

        for dir_name in self.dir_names:
            if self.args.recursive:
                for root, dirs, files in os.walk(
                        dir_name, followlinks=self.args.follow):
                    self.check_dir(root, files)
            else:
                self.check_dir(dir_name, os.listdir(dir_name))

        self.end()
