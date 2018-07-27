#!/usr/bin/env python

# Copyright 2007 Jonas Bengtsson

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
import os, sys, re, zlib, codecs, getopt

def parse(filename):
    "Returns the CRC parsed from the filename or None if no CRC is found"
    crc = re.match(r'.*?\[([a-fA-F0-9]{8})\].*?$', filename) or \
        re.match(r'.*?\(([a-fA-F0-9]{8})\).*?$', filename) or \
        re.match(r'.*?_([a-fA-F0-9]{8})_.*?$', filename)
    if crc:
        return crc.group(1).upper()

def parseline(line, exchange=False):
    "Parses a line from a sfv-file, returns a filename crc tuple"
    match =  re.match(r'([^\;]+)\s([a-fA-F0-9]{8})\s*$', line)
    if match:
        # Make Windows directories into Unix directories
        if exchange:
            return match.group(1).replace('\\', '/'), match.group(2).upper()
        else:
            return match.group(1), match.group(2).upper()

def getcrcs(dirname, fnames, flags):
    "Returns a dict with filename, crc pairs"
    oldcwd = os.getcwdu()
    os.chdir(dirname)

    files = [fname for fname in fnames if os.path.isfile(fname)]
    sfvfiles = [fname for fname in files if fname.lower().endswith('.sfv')]
    crcs = {}

    #If case is to be ignore, build a dictionary with mappings from 
    #filenames with lowercase to the filenames with the real case
    if not flags.case:
        no_case_files = {}

        for fname in files:
            no_case_files[fname.lower()] = fname

    if sfvfiles and flags.sfv:
        for sfvfile in sfvfiles:
            #Almost all sfv-files are encoded with ASCII, but using latin-1 won't
	    #hurt since it's backward compatible
            fobj = codecs.open(sfvfile, 'rb', 'latin-1')
	    for line in fobj:
                result = parseline(line, flags.exchange)
                if result:
                    fname, crc = result
                    if not flags.case and no_case_files.has_key(fname.lower()):
                        crcs[os.path.normpath(no_case_files[fname.lower()])] = crc
                    else:
                        crcs[os.path.normpath(fname)] = crc
            fobj.close()

    if flags.crc:
        for fname in files:
            crc = parse(fname)
            if crc:
                crcs[fname] = crc

    os.chdir(oldcwd)
    return crcs

class Flags:
    "Contains flags that determine how CRC-cheking is done"
    def __init__(self, recursive=False, case=True, exchange=False, 
            sfv=True, crc=True):
        self.recursive = recursive
        self.case = case
        self.exchange = exchange
        self.sfv = sfv
        self.crc = crc

    def parseopt(self, opt, optarg):
        "Allows subclasses to defined new options"
        pass

    def parsecommandline(self, shortopts, longopts):
        """
        Parses arguments and switches from sys.argv and sets variables.
        Returns a tuple of a filename and a directory lists
        """
   	
        longopts.extend(
		['recursive', 'ignore-case', 'exchange', 'no-crc', 'no-sfv'])
        shortopts += 'rixcs'
        opts, args = getopt.gnu_getopt(sys.argv[1:], shortopts, longopts)

        for opt, optarg in opts:
            if opt in ['-r', '--recursive']:
                self.recursive = True
            elif opt in ['-i', '--ignore-case']:
                self.case = False
            elif opt in ['-x', '--exchange']:
                self.exchange = True
            elif opt in ['-c', '--no-crc']:
                self.crc = False
            elif opt in ['-s', '--no-sfv']:
                self.sfv = False
            else:
                self.parseopt(opt, optarg)

        fnames = [arg for arg in args if os.path.isfile(arg)]

        if args:
            dirnames = [arg for arg in args if os.path.isdir(arg)]
        else:
            dirnames = [os.getcwdu()]

        return fnames, dirnames

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
    def __init__(self, flags=None, fnames=None, dirnames=None, blocksize=8192):
        self.fnames = fnames or []
        self.dirnames = dirnames or []
        self.flags = flags or Flags()
        self.blocksize = blocksize
        self.totalstat = Status()

    def crc32_of_file(self, filepath):
        "Returns the CRC of the file filepath"

        fileobj = open(filepath, 'rb')
        self.filestart(fileobj)

        current = 0
        while True:
            self.blockread()
            buf = fileobj.read(self.blocksize)
            if not buf:
                break
            current = zlib.crc32(buf, current)
        fileobj.close()

	#Remove everything except the last 32 bits, also remove the leading 0x
        crc = hex(current&0xFFFFFFFF)[2:].zfill(8).upper()

	#On 32-bit systems hex includes a trailing L
        if crc.endswith("L"):
            return crc[:-1]
        else:
            return crc

    def checkdir(self, dirname, fnames):
        "CRC-check the files in a directory"
        dirlinks = [fname for fname in fnames if os.path.islink(fname) and \
                                                 os.path.isdir(fname)]

        if dirlinks and self.flags.recursive:
            for dirlink in dirlinks:
                os.path.walk(dirlink, Model.checkdir, self)

        crcs = getcrcs(dirname, fnames, self.flags)

        if crcs:
            dirstat = Status(len(crcs))
            self.directorystart(dirname, dirstat)

            for fname, crc in sorted(crcs.items()):
                try:
                    realcrc = self.crc32_of_file(os.path.join(dirname, fname))
                except IOError, eobj:
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

        if self.fnames:
            Model.checkdir(self, os.getcwdu(), self.fnames)

        for dirname in self.dirnames:
            if self.flags.recursive:
                os.path.walk(dirname, Model.checkdir, self)
            else:
                Model.checkdir(self, dirname, os.listdir(dirname))

        self.end()
