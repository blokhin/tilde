#!/usr/bin/env python
#
# Tilde project: cross-platform entry point
# this is a junction; all the end user actions are done from here
# v210513

import sys
import os
import subprocess

if sys.version_info < (2, 6):
    print '\n\nI cannot proceed. Your python is too old. At least version 2.6 is required!\n\n'
    sys.exit()

try: import argparse
except ImportError: import deps.argparse as argparse

try:
    from numpy import dot
    from numpy import array
except ImportError:
    print '\n\nI cannot proceed. Please, install numerical python (numpy)!\n\n'
    sys.exit()

try: import sqlite3
except ImportError:
    try: from pysqlite2 import dbapi2 as sqlite3
    except ImportError:
        print '\n\nI cannot proceed. Please, install python sqlite3 module!\n\n'
        sys.exit()

from settings import settings, repositories, DATA_DIR
from api import API


registered_modules = []
for appname in os.listdir( os.path.realpath(os.path.dirname(__file__) + '/../apps') ):
    if os.path.isfile( os.path.realpath(os.path.dirname(__file__) + '/../apps/' + appname + '/manifest.json') ):
        registered_modules.append(appname)

parser = argparse.ArgumentParser(prog="[tilde_script]", usage="%(prog)s [positional / optional arguments]", epilog="Version: "+API.version, argument_default=argparse.SUPPRESS)

parser.add_argument("path", action="store", help="Scan file(s) / folder(s) / matching-filename(s), divide by space", metavar="PATH(S)/FILE(S)", nargs='*', default=False)
parser.add_argument("-u", dest="daemon", action="store", help="run user interface service (default, prevails over the rest commands if given)", nargs='?', const='shell', default=False, choices=['shell', 'noshell'])
parser.add_argument("-a", dest="add", action="store", help="if PATH(S): add results to current repository", type=bool, metavar="", nargs='?', const=True, default=False)
parser.add_argument("-r", dest="recursive", action="store", help="if PATH(S): scan recursively", type=bool, metavar="", nargs='?', const=True, default=False)
parser.add_argument("-v", dest="verbose", action="store", help="if PATH(S): verbose print", type=bool, metavar="", nargs='?', const=True, default=False)
parser.add_argument("-c", dest="cif", action="store", help="if FILE: save its CIF structure in \"data\" folder", type=bool, metavar="", nargs='?', const=True, default=False)
parser.add_argument("-m", dest="module", action="store", help="if FILE: invoke a module over FILE", nargs='?', const=False, default=False, choices=registered_modules)
parser.add_argument("-f", dest="freqs", action="store", help="if PATH(S): extract and print phonons", type=bool, metavar="", nargs='?', const=True, default=False)

args = parser.parse_args()

# run service daemon if no commands are given
if not args.path and not args.daemon: #if not len(vars(args)):
    args.daemon = 'shell'
if args.daemon:
    print "\nPlease, wait a bit while Tilde application is starting.....\n"

    # invoke windows UI frame
    if args.daemon == 'shell' and 'win' in sys.platform:
       subprocess.Popen(sys.executable + ' ' + os.path.realpath(os.path.dirname(__file__)) + '/winui.py')

    # replace current process with Tilde daemon process
    try:
        os.execv(sys.executable, [sys.executable, os.path.realpath(os.path.dirname(__file__)) + '/daemon.py'])
    except OSError: # taken from Tornado
        os.spawnv(os.P_NOWAIT, sys.executable, [sys.executable, os.path.realpath(os.path.dirname(__file__)) + '/daemon.py'])

    sys.exit()

if not args.path:
    parser.print_help()
    sys.exit()

if args.cif:
    from core.common import write_cif

# if there are commands, run command-line text interface
db = None
if args.add:
    db = sqlite3.connect(os.path.abspath(DATA_DIR + os.sep + settings['default_db']))
    db.row_factory = sqlite3.Row
    db.text_factory = str
    print "The database used:", settings['default_db']

Tilde = API(db_conn=db, filter=settings['filter'], skip_if_path=settings['skip_if_path'])

if settings['filter']: finalized = 'YES'
else: finalized = 'NO'
print "Only finalized:", finalized, "and skip paths if start/end with any of:", settings['skip_if_path']

for target in args.path:

    tasks = Tilde.savvyize(target, recursive=args.recursive, stemma=True)

    for task in tasks:
        filename = os.path.basename(task)
        add_msg = ''

        calc, error = Tilde.parse(task)
        if error:
            print filename, error
            continue

        calc, error = Tilde.classify(calc)
        if error:
            print filename, error
            continue

        if args.add:
            checksum, error = Tilde.save(calc)
            if error:
                print filename, error
                continue
            add_msg = ' added'

        basic_line = filename + " (E=" + str(calc.energy) + ")" + add_msg
        if calc.warns: basic_line += " (" + " ".join(calc.warns) + ")"

        print basic_line

        if args.verbose:
            if calc.convergence:
                print str(calc.convergence)
            if calc.tresholds:
                for i in range(len(calc.tresholds)):
                    print "%1.5f" % calc.tresholds[i][0] + " "*4 + "%1.5f" % calc.tresholds[i][1] + " "*4 + "%1.4f" % calc.tresholds[i][2] + " "*4 + "%1.4f" % calc.tresholds[i][3] + " "*8 + "E=" + "%1.4f" % calc.tresholds[i][4] + " "*8 + "("+str(calc.ncycles[i]) + ")"

        if args.cif and len(tasks) == 1:
            cif_file = os.path.realpath(os.path.abspath(DATA_DIR + os.sep + filename)) + '.cif'
            if write_cif(calc.structures[-1]['cell'], calc.structures[-1]['atoms'], calc['symops'], cif_file):
                print cif_file + " ready"
            else:
                print "Warning! " + cif_file + " cannot be written!"
        
        if args.module and len(tasks) == 1:
            hooks = Tilde.postprocess(calc)
            if args.module not in hooks: print "Module \"" + args.module + "\" is not suitable for this case (outside the scope defined in module manifest)!"
            else:
                print hooks[args.module]['error'] if hooks[args.module]['error'] else hooks[args.module]['data']
            
        if args.freqs:
            if not calc.phonons:
                print 'No phonons here!'
                continue
            for bzpoint, frqset in calc.phonons.iteritems():
                print "*"*25 + bzpoint
                compare = 0
                for i in range(len(frqset)):
                    # if compare == frqset[i]: continue
                    print "%d" % frqset[i] + " (" + calc['irreps'][bzpoint][i] + ")"
                    compare = frqset[i]
        