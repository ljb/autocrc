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

"A commandline interface to autocrc"
import os, sys, getopt
import autocrc

def version():
    "Prints version information"
    print "autocrc v0.3"

def usage():
    "Prints usage information"
    print "Usage:", sys.argv[0], "[OPTION]... [FILE]..."
    print """\
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
  -d\t--directory=DIR\t Use DIR as the working directory
  -v\t--verbose\t Print the calculated CRC and the CRC it was compared aginst
\t\t\t   when mismatches occurs
  -q\t--quiet\t\t Only print error messages and summaries
    \t--version\t Print version information and exit
  -h\t--help\t\t Print this help and exit
  
Exit status is 0 if everything was OK, 1 if a CRC mismatch occured, 2 if files
are missing, 4 if read errors occured. If several errors occured the exit 
status is the sum of the error numbers. For catastrophic failures the exit
status is 255."""

class TextFlags(autocrc.Flags):
    "Flags for the commandline interface"
    def __init__(self, fhelp=False, fversion=False, quiet=False, 
            directory=None, verbose=False):
        autocrc.Flags.__init__(self)
        self.help = fhelp
        self.version = fversion
        self.quiet = quiet
        self.directory = directory or os.getcwd()
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
        elif opt in ['-d', '--directory']:
            os.chdir(optarg)

    def parsetextcommandline(self):
        "Parses a commandline specific for the commandline interface"
        return autocrc.Flags.parsecommandline(self, 'hvqd:', 
			['help', 'version', 'quiet', 'directory=', 'verbose'])

class TextModel(autocrc.Model):
    "Text output"
    def __init__(self, flags, dirnames, fnames, out=sys.stdout):
        autocrc.Model.__init__(self, flags, dirnames, fnames)

        self.out = out
        self.dirstat = None

    def filemissing(self, filename):
        "Print that a file is missing"
        print >> self.out, "%s%*s" % \
                (filename, 78 - len(filename), "No such file")

    def fileok(self, filename):
        "Print that a CRC-check was successful if quiet is false"
        if not self.flags.quiet:
            print >> self.out, "%s%*s" % (filename, 78 - len(filename), " OK")

    def filedifferent(self, filename, crc, realcrc):
        """
        Print that a CRC-check failed. 
        If verbose is set then the CRC calculated and the CRC that it was 
        compared against is also printed
        """
        if self.flags.verbose:
            print >> self.out, "%s%*s" % \
            (filename, 78 - len(filename), " " + realcrc + " != " + crc)
        else:
            print >> self.out, "%s%*s" % \
                (filename, 78 - len(filename), " CRC mismatch")

    def directorystart(self, dirname, dirstat):
        "Print that the CRC-checking of a directory has started"
        self.dirstat = dirstat
        print >> self.out, "Current directory: %s" % \
                os.path.normpath(dirname)

    def directoryend(self):
        "Print a summary of a directory. Has to be called  that was directory"
        print >> self.out, "-"*80

        if self.dirstat.everythingok():
            print >> self.out, "Everything OK"
        else:
            print >> self.out, "Errors occured"
        print >> self.out, \
             "Tested %d files, Successful %d, " \
             "Different %d, Missing %d, Read errors %d\n" % \
             (self.dirstat.nrfiles, self.dirstat.nrsuccessful, 
                     self.dirstat.nrdifferent, self.dirstat.nrmissing, 
                     self.dirstat.nrreaderrors)

    def end(self):
        "Print a total summary if more than one directory was scanned"
        if self.totalstat.nrfiles == 0:
            print >> self.out, "No CRC-sums found"
        
        elif self.totalstat.nrdirs > 1:
            if self.totalstat.everythingok():
                print >> self.out, "Everything OK"
            else:
                print >> self.out, "Errors Occured"
            print >> self.out, "  Tested\t %d files" % self.totalstat.nrfiles 
            print >> self.out, "  Successful\t %d files" % \
                    self.totalstat.nrsuccessful
            print >> self.out, "  Different\t %d files" % \
                    self.totalstat.nrdifferent
            print >> self.out, "  Missing\t %d files" % self.totalstat.nrmissing
            print >> self.out, "  Read Errors\t %d files" % \
                    self.totalstat.nrreaderrors

        #Explained in usage()
        sys.exit((self.totalstat.nrdifferent > 0) + 
            (self.totalstat.nrmissing > 0) * 2 +
            (self.totalstat.nrreaderrors > 0) * 4)

def main():
    "The main function"
    try:
        flags = TextFlags()
        fnames, dirnames = flags.parsetextcommandline()
        model = TextModel(flags, fnames, dirnames)
        model.run()

    except getopt.GetoptError, eobj:
        print >> sys.stderr, "autocrc:", eobj.msg
        print >> sys.stderr, "Try", sys.argv[0], "-h for more information"
        sys.exit(255)
    except OSError, eobj:
        print >> sys.stderr, "autocrc:", eobj.filename + ":", eobj.strerror
        sys.exit(255)
    except KeyboardInterrupt: pass

if __name__ == '__main__':
    main()
