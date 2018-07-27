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

"A commandline interface to autocrc"
import os, sys, optparse
import autocrc

class TextParser(autocrc.AutoParser):
    "Flags for the commandline interface"
    def __init__(self):
        super().__init__()

        self.add_option("-q", "--quiet", action="store_true",
            help="Only print error messages and summaries")
        self.add_option("-v", "--verbose", action="store_true",
            help="Print the calculated CRC and the CRC it was compared against when mismatches occurs")

class TextModel(autocrc.Model):
    def filemissing(self, filename):
        "Print that a file is missing"
        self.fileprint(filename, "No such file")

    def fileok(self, filename):
        "Print that a CRC-check was successful if quiet is false"
        if not self.flags.quiet:
            self.fileprint(filename, "OK")

    def filedifferent(self, filename, crc, realcrc):
        """
        Print that a CRC-check failed. 
        If verbose is set then the CRC calculated and the CRC that it was 
        compared against is also printed
        """
        if self.flags.verbose:
            self.fileprint(filename, realcrc + " != " + crc)
        else:
            self.fileprint(filename, "CRC mismatch")
		
    def filereaderror(self, filename):
        "Print that a read error occured"
        self.fileprint(filename, "Read error")

    def directorystart(self, dirname, dirstat):
        "Print that the CRC-checking of a directory has started"
        self.dirstat = dirstat
        if dirname == os.curdir:
            dirname = os.path.abspath(dirname)
        else:
            dirname = os.path.normpath(dirname)
        print("Current directory:", dirname)

    def directoryend(self):
        "Print a summary of a directory."
        print("-"*80)

        if self.dirstat.everythingok():
            print("Everything OK")
        else:
            print("Errors occured")
        print(
             "Tested {0} files, Successful {1}, " \
             "Different {2}, Missing {3}, Read errors {4}\n".format(
                     self.dirstat.nrfiles, self.dirstat.nrsuccessful,
                     self.dirstat.nrdifferent, self.dirstat.nrmissing,
                     self.dirstat.nrreaderrors))

    def end(self):
        "Print a total summary if more than one directory was scanned"
        if self.totalstat.nrfiles == 0:
            print("No CRC-sums found")
        
        elif self.totalstat.nrdirs > 1:
            if self.totalstat.everythingok():
                print("Everything OK")
            else:
                print("Errors Occured")
            print("  Tested\t", self.totalstat.nrfiles, "files")
            print("  Successful\t", self.totalstat.nrsuccessful, "files")
            print("  Different\t", self.totalstat.nrdifferent, "files")
            print("  Missing\t", self.totalstat.nrmissing, "files")
            print("  Read Errors\t", self.totalstat.nrreaderrors, "files")

        #Set the exit status to the value explained in usage()
        sys.exit((self.totalstat.nrdifferent > 0) + 
            (self.totalstat.nrmissing > 0) * 2 +
            (self.totalstat.nrreaderrors > 0) * 4)

    def fileprint(self, filename, status):
        padlen = max(0, 77 - len(filename))
        normfname = os.path.normpath(filename)
        print("{0} {1:>{2}}".format(normfname, status, padlen))

def main():
    "The main function"
    try:
        parser = TextParser()
        flags, fnames, dirnames = parser.parse_args()
        parser.destroy()
        model = TextModel(flags, fnames, dirnames)
        model.run()

    except OSError as eobj:
        print("autocrc:", eobj.filename + ":", eobj.strerror, file=sys.stderr)
        sys.exit(8)
    except KeyboardInterrupt: pass

if __name__ == '__main__':
    main()
