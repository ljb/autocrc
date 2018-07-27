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
The core of autocrc. Performes the CRC-checks independent of what kind
of interface is used
"""
import os, sys, re, zlib, mmap, optparse

class AutoParser(optparse.OptionParser):
    "Parse flags from the commandline"
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
            default=True,help="do not parse CRC-sums from filenames")
        self.add_option("-s", "--no-sfv", action="store_false", dest="sfv",
            default=True,help="do not parse CRC-sums from sfv-files")
        self.add_option("-C", "--directory",
            metavar="DIR", help="use DIR as the working directory")
        self.add_option("-L", "--follow", action="store_true",
            help="follow symbolic directory links in recursive mode")

    def parse_args(self):
        flags, args = super().parse_args()
        fnames = [arg for arg in args if os.path.isfile(arg)]
        dirnames = [arg for arg in args if os.path.isdir(arg)] if args \
              else [os.curdir]
        return flags, fnames, dirnames

class Status:
    "Contains status information"
    def __init__(self, nrfiles=0):
        self.nrmissing = 0
        self.nrdifferent = 0
        self.nrsuccessful = 0
        self.nrreaderrors = 0
        self.nrdirs = 0
        self.nrfiles = nrfiles

    def update(self, other):
        "Update status with data from another Status instance"
        self.nrmissing += other.nrmissing
        self.nrdifferent += other.nrdifferent
        self.nrsuccessful += other.nrsuccessful
        self.nrreaderrors += other.nrreaderrors
        self.nrdirs += 1
        self.nrfiles += other.nrfiles

    def everythingok(self):
        "Returns true if no everything is ok"
        return self.nrreaderrors == self.nrdifferent == self.nrmissing == 0

class Model:
    "An abstract model. Subclasses decides how the output is presented"
    def __init__(self, flags, fnames=[], dirnames=[], blocksize=8192):
        self.flags = flags
        self.fnames = fnames
        self.dirnames = dirnames
        self.blocksize = blocksize
        self.totalstat = Status()

    def parse(self, filename):
        "Returns the CRC parsed from the filename or None if no CRC is found"
        crc = re.match(r'.*?\[([a-fA-F0-9]{8})\].*?$', filename) or \
            re.match(r'.*?\(([a-fA-F0-9]{8})\).*?$', filename) or \
            re.match(r'.*?_([a-fA-F0-9]{8})_.*?$', filename)
        if crc:
            return crc.group(1).upper()

    def parseline(self, line):
        "Parses a line from a sfv-file, returns a filename crc tuple"
        match =  re.match(r'([^\;]+)\s([a-fA-F0-9]{8})\s*$', line)
        if match:
            # Make Windows directories into Unix directories
            if self.flags.exchange:
                return match.group(1).replace('\\', '/'), match.group(2).upper()
            else:
                return match.group(1), match.group(2).upper()

    def getcrcs(self, dirname, fnames):
        "Returns a dict with filename, crc pairs"
        oldcwd = os.getcwd()
        os.chdir(dirname)

        files = [fname for fname in fnames if os.path.isfile(fname)]
        sfvfiles = [fname for fname in files if fname.lower().endswith('.sfv')]
        crcs = {}

        #If case is to be ignore, build a dictionary with mappings from 
        #filenames with lowercase to the filenames with the real case
        if not self.flags.case:
            no_case_files = {}

            for fname in files:
                no_case_files[fname.lower()] = fname

        if sfvfiles and self.flags.sfv:
            for sfvfile in sfvfiles:
                fobj = open(sfvfile, 'r', errors='replace')
                for line in fobj:
                    result = self.parseline(line)
                    if result:
                        fname, crc = result
                        if not self.flags.case and fname.lower() in no_case_files:
                            crcs[no_case_files[fname.lower()]] = crc
                        else:
                            crcs[fname] = crc

        if self.flags.crc:
            for file in files:
                crc = self.parse(file)
                if crc:
                    crcs[file] = crc

        os.chdir(oldcwd)
        return crcs

    def crc32_of_file(self, filepath):
        "Returns the CRC of the file filepath"

        fileobj = open(filepath, 'r+')
        mapobj = mmap.mmap(fileobj.fileno(), 0, access=mmap.ACCESS_READ)
#        current = zlib.crc32(mapobj)

#        fileobj = open(filepath, 'rb')
        self.filestart(fileobj)

        current = 0
        while True:
            buf = mapobj.read(self.blocksize)
            if not buf:
                break
            current = zlib.crc32(buf, current)
            self.blockread()
        fileobj.close()
        mapobj.close()

	#Remove everything except the last 32 bits, including the leading 0x
        return hex(current&0xFFFFFFFF)[2:].upper().zfill(8)

    def checkdir(self, dirname, fnames):
        "CRC-check the files in a directory"
        crcs = self.getcrcs(dirname, fnames)

        if crcs:
            dirstat = Status(len(crcs))
            self.directorystart(dirname, dirstat)

            for fname, crc in sorted(crcs.items()):
                try:
                    realcrc = self.crc32_of_file(os.path.join(dirname, fname))

                except IOError as eobj:
                    if eobj.errno == 2:
                        dirstat.nrmissing += 1
                        self.filemissing(fname)
                    else:
                        dirstat.nrreaderrors += 1
                        self.filereaderror(fname)
                else:
                    if crc == realcrc:
                        dirstat.nrsuccessful += 1
                        self.fileok(fname)
                    else:
                        dirstat.nrdifferent += 1
                        self.filedifferent(fname, crc, realcrc)
            
            self.totalstat.update(dirstat)
            self.directoryend()

    #Hook methods, implemented by subclasses
    def fileok(self, filename):
        "Called when a file was successfully CRC-checked"
        pass

    def filemissing(self, filename):
        "Called when a file is missing"
        pass

    def filereaderror(self, filename):
        "Called when a read error occurs on a file"    
        pass
    
    def filedifferent(self, filename, crc, realcrc):
        "Called when a CRC-mismatch occurs"
        pass
    
    def directorystart(self, dirname, dirstat):
        "Called when the CRC-checks on a directory is started"
        pass

    def directoryend(self):
        "Called when the CRC-checks on a directory is complete"
        pass

    def start(self):
        "Called when the CRC-checking starts"
        pass

    def end(self):
        "Called when the CRC-checking is complete"
        pass

    def filestart(self, fileobj):
        "Called when the CRC-checking of a file is started"

    def blockread(self):
        "Called reguarly in the loop where autocrc spends most of it's time."
        pass

    def run(self):
        "Starts the CRC-checking"

        self.start()

        if self.flags.directory:
            os.chdir(self.flags.dirname)

        #Mapping from a directory name to a list with the files that are
        #to be CRC-checked in that directory
        dirfilemap = {}
        for fname in self.fnames:
            head, tail = os.path.split(fname)
            head = os.path.abspath(head)
            if head not in dirfilemap:
                dirfilemap[head] = []
            dirfilemap[head].append(tail)

        for dirname, fnames in dirfilemap.items():
            self.checkdir(dirname, fnames)

        for dirname in self.dirnames:
            if self.flags.recursive:
                for root, dirs, files in os.walk(
		        dirname, followlinks=self.flags.follow):
                    self.checkdir(root, files)
            else:
                self.checkdir(dirname, os.listdir(dirname))

        self.end()
