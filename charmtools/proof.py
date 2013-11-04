#!/usr/bin/python

#    Copyright (C) 2011 - 2013  Canonical Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import argparse

from bundles import Bundle
from charms import Charm
from cli import parser_defaults


def get_args(args):
    parser = argparse.ArgumentParser(
        description='Performs static analysis on charms and bundles')
    parser.add_argument('-n', '--offline', action='store_true',
                        help='Only perform offline proofing')
    parser.add_argument('charm_name', nargs='?', default=os.getcwd(),
                        help='path of charm dir to check. Defaults to PWD')
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def proof(args=None):
    args = get_args(args)
    name = args.charm_name
    if not args.bundle:
        try:
            c = Charm(os.path.abspath(name))
        except:
            try:
                c = Bundle(os.path.abspath(name), args.debug)
            except Exception as e:
                print "Not a Bundle or a Charm, can not proof"
                sys.exit(1)
    else:
        try:
            c = Bundle(os.path.abspath(name), args.debug)
        except Exception as e:
            print e.msg
            sys.exit(1)

    lint, err_code = c.proof()
    return lint, err_code


def main():
    lint, exit_code = proof()
    if lint:
        print "\n".join(lint)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
