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
import re
import argparse

from . import charms
from .mr import Mr


def setup_parser():
    parser = argparse.ArgumentParser(prog='charm update',
                                     description='Update charm_directory with '
                                     'latest from Charm Store')
    parser.add_argument('charm_directory', nargs='?',
                        help='Path to where all charms are stored')
    parser.add_argument('-f', '--fix', action='store_true',
                        help='Attempt to fix charms in charm_directory')

    return parser


def update(charm_dir, fix=False):
    mr = Mr(charm_dir)
    for charm in charms.remote():
        if re.match('^lp:charms\/', charm):
            charm_name = os.path.basename(charm)
            if mr.exists(charm_name) and fix:
                mr.update(charm_name, force=True)
                continue
            mr.add(charm_name, charm)
    try:
        mr.save()
    except Exception as e:
        raise Exception(".mrconfig not saved: %s" % e.strerror)


def main():
    parser = setup_parser()
    args = parser.parse_args()

    print 'Pulling charm list from Launchpad'

    try:
        update(args.charm_directory, args.fix)
    except Exception as e:
        # Got this from http://stackoverflow.com/q/5574702/196832
        print >> sys.stderr, ".mrconfig not saved: ", e
        sys.exit(1)


if __name__ == '__main__':
    main()
