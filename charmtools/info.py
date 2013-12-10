#!/usr/bin/python

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

import re
import argparse

from cli import parser_defaults
from charmworldlib import charm


def info(charm_id, is_bundle=False):
    c = charm.Charm(charm_id)
    readme = [s for s in c.files if re.match("^readme", s, re.IGNORECASE)]

    if not readme:
        raise Exception('No README found')

    return c.file(readme[0])


def setup_parser(args=None):
    parser = argparse.ArgumentParser(
        description='Learn more about a Charm or Bundle')
    parser.add_argument('charm', nargs=1, help='Charm to branch',
                        metavar=('charm_name'))
    parser = parser_defaults(parser)

    return parser.parse_args(args)


def main():
    a = setup_parser()
    charm_id = a.charm[0].replace('cs:', '')

    try:
        print info(charm_id)
    except Exception as e:
        print e.strerror


if __name__ == '__main__':
    main()
