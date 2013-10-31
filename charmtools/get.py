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

from .mr import Mr
from . import charms


def setup_parser():
    parser = argparse.ArgumentParser(prog='charm get',
                                     description='Retrieves official charm '
                                                 'branch from launchpad.net')
    parser.add_argument('charm', nargs=1, help='Charm to branch',
                        metavar=('charm_name'))
    parser.add_argument('branch_to', nargs='?',
                        help='Path to where charm should be branched')

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    charm = args.charm[0]
    ldir = args.branch_to
    branch_dir = os.path.realpath(ldir) if ldir else os.getcwd()

    if "lp:charms/%s" % charm not in charms.remote():
        sys.stderr.write('Error: %s not found in charm store.\n' % charm)
        sys.exit(1)

    charm_dir = os.path.join(branch_dir, charm)
    if os.path.exists(charm_dir) and os.listdir(charm_dir):
        sys.stderr.write('Error: %s exists and is not empty\n' % charm_dir)

    if not os.path.exists(branch_dir):
        os.makedirs(branch_dir)

    try:
        mr = Mr(branch_dir, mr_compat=False)
        sys.stderr.write('Branching %s to %s\n' % (charm, branch_dir))
        mr.add(charm, checkout=True)
    except Exception as e:
        print >> sys.stderr, "Error during branching: ", e
