#!/usr/bin/env python

from distutils.core import setup

setup(name='autocrc',
        version='1.4',
        author='Jonas Bengtsson',
        description = 'Automated CRC-checking',
        author_email='jonasb@linux.se',
        package_dir = {'autocrc' : 'src'},
        packages = ['autocrc'],
        url='http://sourceforge.net/projects/autocrc',
        scripts = ['scripts/autocrc', 'scripts/gautocrc'],
        license="GPLv3",
        long_description = """
        autocrc uses 32-bit CRC-sums to verify the integrity of files.
        The CRC-sums are parsed both from filenames and from sfv files.
        autocrc can perform CRC-checks recursively. After it's done, it prints
        a summary of the result.
        """)
