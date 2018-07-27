#!/usr/bin/env python3

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

"A commandline interface to autocrc"
import os, sys, getopt
import autocrc

def version():
    "Prints version information"
    print("autocrc v0.4")

def usage():
    "Prints usage information"
    print("Usage:", sys.argv[0], "[OPTION]... [FILE]...")
    print("""\
CRC-check FILEs.
If no files are given, CRC-checks are performed on all the files in the working
directory.

Mandatory arguments to long options are mandatory for short options too.
  -r\t--recursive\t CRC-check recursively
  -i\t--ignore-case\t Ignore case for filenames parsed from sfv-files
  -x\t--exchange\t Interpret \\ as / for filenames parsed from sfv-files
\t\t\t   Has no effect on Windows-like systems
  -c\t--no-crc\t Do not parse CRC-sums from filenames
  -s\t--no-sfv\t Do not parse CRC-sums from sfv-files
  -C\t--directory=DIR\t Use DIR as the working directory
  -L\t--follow\t Follow symbolic links
  -v\t--verbose\t Print the calculated CRC and the CRC it was compared against
\t\t\t   when mismatches occurs
  -q\t--quiet\t\t Only print error messages and summaries
    \t--version\t Print version information and exit
  -h\t--help\t\t Print this help and exit
  
Exit status is 0 if everything was OK, 1 if a CRC mismatch occured, 2 if files
were missing, 4 if read errors occured. If several errors occured the exit 
status is the sum of the error numbers. For catastrophic failures the exit
status is 255.""")

class TextFlags(autocrc.Flags):
    "Flags for the commandline interface"
    def __init__(self, help=False, version=False, quiet=False, verbose=False):
        super().__init__()
        self.help = help
        self.version = version
        self.quiet = quiet
        self.verbose = verbose

    def parseopt(self, opt, optarg):
        "Parses the options specific for a commandline interface"
        if opt in ['-h', '--help']:
            usage()
            sys.exit(0)
        elif opt in ['--version']:
            version()
            sys.exit(0)
        elif opt in ['-q', '--quiet']:
            self.quiet = True
        elif opt in ['-v', '--verbose']:
            self.verbose = True

    def parsetextcommandline(self):
        "Parses a commandline specific for the commandline interface"
        return super().parsecommandline('hvq', 
	    ['help', 'version', 'quiet', 'verbose'])

class TextModel(autocrc.Model):
    "Text output"
    def __init__(self, flags, dirnames, fnames):
        super().__init__(flags, dirnames, fnames)

        self.dirstat = None

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
        print("Current directory:", os.path.normpath(dirname))

    def directoryend(self):
        "Print a summary of a directory."
        print("-"*80)

        if self.dirstat.everythingok():
            print("Everything OK")
        else:
            print("Errors occured")
        print(\
             "Tested {0} files, Successful {1}, " \
             "Different {2}, Missing {3}, Read errors {4}\n".format(\
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
      print("{0} {1:>{2}}".format(filename, status, padlen))

def main():
    "The main function"
    try:
        flags = TextFlags()
        fnames, dirnames = flags.parsetextcommandline()
        model = TextModel(flags, fnames, dirnames)
        model.run()

    except getopt.GetoptError as eobj:
        print("autocrc:", eobj.msg, file=sys.stderr)
        print("Try", sys.argv[0], "-h for more information", file=sys.stderr)
        sys.exit(255)
    except OSError as eobj:
        print("autocrc:", eobj.filename + ":", eobj.strerror, file=sys.stderr)
        sys.exit(255)
    except KeyboardInterrupt: pass

if __name__ == '__main__':
    main()
