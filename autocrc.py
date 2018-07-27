#!/usr/bin/env python

# Copyright 2007 Jonas Bengtsson

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"Automated CRC-checking"
import sys, getopt, os, re, zlib, fileinput

#Set by the use of switches
__recursive__ = __exchange__ = __quiet__ = False
__case__ = __crc__ = __sfv__ = True

def crc32_of_file(filepath):
    "Returns the CRC of the file filepath"
    fileobj = open(filepath, 'rb')
    current = 0
    while True:
        buf = fileobj.read(8192)
        if not buf:
            break
        current = zlib.crc32(buf, current)
    fileobj.close()
    return str(hex(current&0xFFFFFFFF))[2:-1].zfill(8).upper()

def parse(filename):
    "Returns the CRC parsed from the filename or None if no CRC is found"
    crc = re.match(r'.*?\[([a-fA-F0-9]{8})\].*?$', filename) or \
          re.match(r'.*?\(([a-fA-F0-9]{8})\).*?$', filename) or \
          re.match(r'.*?_([a-fA-F0-9]{8})_.*?$', filename)
    if crc:
        return crc.group(1).upper()

def parseline(line):
    "Parses a line from a sfv-file, returns a filename crc tuple"
    match =  re.match(r'([^\;]+)\s([a-fA-F0-9]{8})\s*$', line)
    if match:
        # Make Windows directories into Unix directories
        if __exchange__:
            return match.group(1).replace('\\', '/'), match.group(2).upper()
        else:
            return match.group(1), match.group(2).upper()

def getcrcs(dirname, fnames):
    "Returns a dict with filename, crc pairs"
    oldcwd = os.getcwd()
    os.chdir(dirname)

    files = [fname for fname in fnames if os.path.isfile(fname)]
    sfvfiles = [fname for fname in files if fname.lower().endswith('.sfv')]
    crcs = {}

    #If case is to be ignore, build a dictionary with mappings from filenames
    #with lowercase to the filenames with the real case
    if not __case__:
        no_case_files = {}

        for fname in files:
            no_case_files[fname.lower()] = fname

    if sfvfiles and __sfv__:
        for line in fileinput.input(sfvfiles):
            result = parseline(line)
            if result:
                fname, crc = result
                if not __case__ and no_case_files.has_key(fname.lower()):
                    crcs[os.path.normpath(no_case_files[fname.lower()])] = crc
                else:
                    crcs[os.path.normpath(fname)] = crc

    if __crc__:
        for fname in files:
            crc = parse(fname)
            if crc:
                crcs[fname] = crc

    os.chdir(oldcwd)
    return crcs

def checkdir(status, dirname, fnames):
    "CRC-check the files in a directory"
    dirlinks = [fname for fname in fnames if os.path.islink(fname) and\
                                             os.path.isdir(fname)]

    if dirlinks and __recursive__:
        for dirlink in dirlinks:
            os.path.walk(dirlink, checkdir, status)

    crcs = getcrcs(dirname, fnames)

    if crcs:
        nrsuccessful = nrdifferent = nrmissing = 0
        print "Current directory: %s" % os.path.normpath(dirname)
        for fname, crc in sorted(crcs.items()):
            try:
                realcrc = crc32_of_file(os.path.join(dirname, fname))
            except IOError, eobj:
                #emsg = "No such file" if eobj.errno == 2 else eobj.strerror
                if eobj.errno == 2:
                    errormessage = "No such file"
                else:
                    errormessage = eobj.strerror
                print "%s%*s" % (fname, 78 - len(fname), " " + errormessage)
                nrmissing += 1
            else:
                if crc == realcrc:
                    if not __quiet__:
                        print "%s%*s" % (fname, 78 - len(fname), " OK")
                    nrsuccessful += 1
                else:
                    print "%s%*s" % (fname, 78 - len(fname), " CRC mismatch")
                    nrdifferent += 1

        print "-"*80

        if nrdifferent == nrmissing == 0:
            print "Everything OK"
        else:
            print "Errors occured"
        print "Tested %d files, Successful %d, Different %d, Missing %d\n" % \
                  (len(crcs), nrsuccessful, nrdifferent, nrmissing)

        status["Missing"] += nrmissing
        status["Successful"] += nrsuccessful
        status["Different"] += nrdifferent
        status["Total"] += len(crcs)
        status["Directories"] += 1

def version():
    "Prints version information"
    print "autocrc v0.2"

def usage():
    "Prints usage information"
    print "Usage:", sys.argv[0], "[OPTION]... [FILE]..."
    print """CRC-check FILEs.
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
  -q\t--quiet\t\t Only print error messages and summaries
  -v\t--version\t Print version information and exit
  -h\t--help\t\t Print this help and exit"""

def summary(status):
    "Print a summary"
    if status["Total"] == 0:
        print "No CRC-sums found"
    #Print a summary only if more than one directory contained files with crcs
    elif status["Directories"] > 1:
        if status["Missing"] == status["Different"] == 0:
            print "Everything OK"
        else:
            print "Errors Occured"
        print "  Tested\t %d files" % status["Total"]
        print "  Successful\t %d files" % status["Successful"]
        print "  Different\t %d files" % status["Different"]
        print "  Missing\t %d files" % status["Missing"]

def parsecommandline():
    """
    Parses arguments and switches from sys.argv and sets global variables.
    "Returns a tuple of a filename and a directory list
    """

    global __case__, __recursive__, __exchange__, __quiet__, __sfv__, __crc__

    opts, args = getopt.gnu_getopt(sys.argv[1:], 'rihxvqcsd:', \
    ['recursive', 'ignore-case', 'help', 'exchange', \
    'version', 'quiet', 'no-crc', 'no-sfv', 'directory='])

    for opt, optarg in opts:
        if opt in ['-h', '--help']:
            usage()
            sys.exit(0)
        elif opt in ['-v', '--version']:
            version()
            sys.exit(0)
        elif opt in ['-r', '--recursive']:
            __recursive__ = True
        elif opt in ['-i', '--ignore-case']:
            __case__ = False
        elif opt in ['-x', '--exchange']:
            __exchange__ = True
        elif opt in ['-q', '--quiet']:
            __quiet__ = True
        elif opt in ['-c', '--no-crc']:
            __crc__ = False
        elif opt in ['-s', '--no-sfv']:
            __sfv__ = False
        elif opt in ['-d', '--directory']:
            os.chdir(optarg)

    fnames = [arg for arg in args if os.path.isfile(arg)]

    if args:
        dirnames = [arg for arg in args if os.path.isdir(arg)]
    else:
        dirnames = [os.getcwd()]

    return fnames, dirnames

def main():
    "The main function"
    try:
        fnames, dirnames = parsecommandline()

        status = {"Total":0, "Missing":0, "Successful":0, "Different":0,
                  "Directories":0}

        if fnames:
            checkdir(status, os.getcwd(), fnames)

        for dirname in dirnames:
            if __recursive__:
                os.path.walk(dirname, checkdir, status)
            else:
                checkdir(status, dirname, os.listdir(dirname))

        summary(status)
        if status["Missing"] == status["Different"] == 0:
            sys.exit(0)

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
