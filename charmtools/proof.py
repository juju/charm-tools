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
from charmtools import utils


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description='perform static analysis on a charm or bundle')
    parser.add_argument('charm_name', nargs='?', default=os.getcwd(),
                        help='path of charm dir to check. Defaults to PWD')
    utils.add_plugin_description(parser)
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def proof(path, is_bundle, debug):
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

    lint, err_code = c.proof()
    return lint, err_code


def main():
    args_ = get_args()
    lint, exit_code = proof(args_.charm_name, args_.bundle, args_.debug)
    if lint:
        print("\n".join(lint))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
