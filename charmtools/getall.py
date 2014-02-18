#!/usr/bin/env python
# Copyright (C) 2013 Marco Ceppi <marco@ceppi.net>.
#
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

import os
import sys
import argparse
import subprocess

from .mr import Mr
from .cli import ext


def setup_parser():
    parser = argparse.ArgumentParser(prog='juju charm getall',
                                     description='Retrieves all charms from '
                                                 'Launchpad')
    parser.add_argument('charms_directory', nargs='?',
                        help='Path to where all charms should be downloaded')

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if not args.charms_directory:
        sys.stderr.write('Error: No value for charms_directory provided\n\n')
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.charms_directory):
        os.makedirs(args.charms_directory, 0o755)

    update_cmd = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                              'charm-update%s' % ext())
    charm_update = subprocess.call([update_cmd, args.charms_directory])
    if charm_update != 0:
        sys.stderr.write('Unable to perform `juju charm update`!\n')
        sys.exit(1)

    try:
        mr = Mr(directory=args.charms_directory)
        sys.stderr.write('Grabbing %s charms from Charm Store\n' %
                         len(mr.list()))
        for charm in mr.list():
            sys.stderr.write('Branching %s\n' % charm)
            try:
                mr.update(charm)
            except (KeyboardInterrupt, SystemExit):
                sys.stderr.write('\nKeyboard Interrupt caught. Exiting!\n')
                break
            except Exception as e:
                print >> sys.stderr, "Error during update: ", e
    except Exception as e:
        print >> sys.stderr, "Error during setup: ", e
