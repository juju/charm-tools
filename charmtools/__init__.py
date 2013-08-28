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
import glob

import subprocess

ext = ''
if os.name == 'nt':
    ext = '.exe'


def usage(exit_code=0):
    sys.stderr.write('usage: %s subcommand\n' % sys.argv[0])
    subs = subcommands(os.path.dirname(os.path.realpath(__file__)))
    sys.stderr.write('\n  Available subcommands are:\n    ')
    sys.stderr.write('\n    '.join(subs))
    sys.stderr.write('\n')
    sys.exit(exit_code)


def subcommands(scripts_dir):
    subs = []
    for path in os.environ['PATH'].split(os.pathsep):
        path = path.strip('"')
        for cmd in glob.glob(os.path.join(path, 'juju-charm-*%s' % ext)):
            sub = os.path.basename(cmd)
            sub = sub.split('juju-charm-')[1].replace(ext, '')
            subs.append(sub)

    subs.sort()
    # Removes blacklisted items from the subcommands list.
    return filter(lambda s: s not in ['mr', 'charms'], subs)


def main():
    #print sys.argv
    if len(sys.argv) < 2:
        usage(1)

    sub = sys.argv[1]
    opts = sys.argv[2:]
    sub_exec = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])),
               "juju-charm-%s%s" % (sub, ext))
    #print sub_exec
    if not os.path.exists(sub_exec):
        sys.stderr.write('Error: %s is not a valid subcommand\n\n' % sub)
        usage(2)
    subprocess.call([sub_exec] + opts)


if __name__ == '__main__':
    main()
