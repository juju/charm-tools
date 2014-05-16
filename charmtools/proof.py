#!/usr/bin/python

#    Copyright (C) 2011 - 2014  Canonical Ltd.
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


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description='Performs static analysis on charms and bundles')
    parser.add_argument('-n', '--offline', action='store_false',
                        help='Only perform offline proofing')
    parser.add_argument('--server', default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument('--port', default=None, type=int,
                        help=argparse.SUPPRESS)
    parser.add_argument('--secure', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('charm_name', nargs='?', default=os.getcwd(),
                        help='path of charm dir to check. Defaults to PWD')
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def proof(path, is_bundle, with_remote, debug, server, port, secure):
    path = os.path.abspath(path)
    if not is_bundle:
        try:
            c = Charm(path)
        except:
            try:
                c = Bundle(path, debug)
            except Exception as e:
                return ["FATAL: Not a Bundle or a Charm, can not proof"], 200
    else:
        try:
            c = Bundle(path, debug)
        except Exception as e:
            return ["FATAL: %s" % e.message], 200

    lint, err_code = c.proof(
        remote=with_remote, server=server, port=port, secure=secure)
    return lint, err_code


def main():
    args_ = get_args()
    lint, exit_code = proof(args_.charm_name, args_.bundle, args_.offline,
                            args_.debug, args_.server, args_.port,
                            args_.secure)
    if lint:
        print "\n".join(lint)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
