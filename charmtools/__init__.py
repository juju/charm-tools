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

import subprocess

from . import cli
from . import version


def charm():
    if len(sys.argv) < 2:
        cli.usage(1)

    sub = sys.argv[1]
    opts = sys.argv[2:]
    if sub == '--description':
        sys.stdout.write("Tools for authoring and maintaining charms\n")
        sys.exit(0)

    if sub == '--help':
        cli.usage(0)

    if sub == '--version':
        version.main()
        sys.exit(0)

    if sub == '--list':
        print '\n'.join(cli.subcommands(os.path.realpath(__file__)))
        sys.exit(0)

    sub_exec = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            "charm-%s%s" % (sub, cli.ext()))

    if not os.path.exists(sub_exec):
        sys.stderr.write('Error: %s is not a valid subcommand\n\n' % sub)
        cli.usage(2)
    sys.exit(subprocess.call([sub_exec] + opts))


def bundle():
    if len(sys.argv) < 2:
        cli.usage(0)

    sub = sys.argv[1]
    opts = sys.argv[2:]

    if sub == '--description':
        sys.stdout.write("Tools for managing bundles\n")
        sys.exit(0)

    if sub == '--help':
        cli.usage(0)

    sub_exec = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
                            "charm-%s%s" % (sub, cli.ext()))

    if not os.path.exists(sub_exec):
        sys.stderr.write('Error: %s is not a valid subcommand\n\n' % sub)
        cli.usage(2)

    sys.exit(subprocess.call([sub_exec, '--bundle'] + opts))


if __name__ == '__main__':
    charm()
