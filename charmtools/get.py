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

from mr import Mr
from charmworldlib import charm as cwc


def setup_parser():
    parser = argparse.ArgumentParser(prog='charm get',
                                     description='Retrieves official charm '
                                                 'branch from launchpad.net')
    parser.add_argument('charm', nargs=1, help='Charm to branch',
                        metavar=('charm_name'))
    parser.add_argument('branch_to', nargs='?',
                        help='Path to where charm should be branched')

    return parser


def parse_charm_id(charm_id):
    if charm_id.startswith('cs:'):
        charm_id = charm_id.replace('cs:', '')

    try:
        charm = cwc.Charm(charm_id)
    except:
        return None

    return charm


def download(charm, to):
    charm_dir = os.path.join(to, charm.name)
    if os.path.exists(charm_dir) and os.listdir(charm_dir):
        raise ValueError('%s exists and is not empty' % charm_dir)

    if not os.path.exists(to):
        os.makedirs(to)

    mr = Mr(to, mr_compat=False)
    mr.add(charm.name, charm.code_source['location'], checkout=True)


def main(args=None):
    parser = setup_parser()
    args = parser.parse_args(args)

    charm = parse_charm_id(args.charm[0])

    if not charm:
        sys.stderr.write('Error: %s not found in charm store\n'
                         % args.charm[0])
        sys.exit(1)

    ldir = args.branch_to
    branch_dir = os.path.realpath(ldir) if ldir else os.getcwd()

    sys.stderr.write('Branching %s (%s) to %s/%s\n' % (charm.name,
                     charm.code_source['location'], branch_dir,
                     charm.name))

    try:
        download(charm, branch_dir)
    except Exception as e:
        sys.stderr.write('Error: %s' % str(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
