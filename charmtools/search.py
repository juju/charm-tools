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

import argparse

from . import charms


def setup_parser():
    parser = argparse.ArgumentParser(prog='charm search',
                                     description='Match name against all '
                                     'charms (official and personal) in store')
    parser.add_argument('name', nargs=1, help='Name which to search by')

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()
    matches = [c for c in charms.remote() if args.name[0] in c]
    print '\n'.join(matches)
