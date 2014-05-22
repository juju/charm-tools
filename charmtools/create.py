#!/usr/bin/python
#
#    create - generate Juju charm from template
#
#    Copyright (C) 2011  Canonical Ltd.
#    Author: Clint Byrum <clint.byrum@canonical.com>
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

import logging
import os
import sys
import os.path as path
import time
import shutil
import tempfile
import argparse

from Cheetah.Template import Template
from stat import ST_MODE

from charmtools.generators import (
    CharmGenerator,
    CharmGeneratorException,
    CharmTemplate,
)

log = logging.getLogger(__name__)


def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('charmname', help='Name of charm to create.')
    parser.add_argument('charmhome', nargs='?',
                        help='Dir to create charm in. Defaults to CHARM_HOME '
                        'env var or PWD')
    parser.add_argument('-t', '--template', default='bash')
    parser.add_argument('-c', '--config')

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()
    args.charmhome = args.charmhome or os.getenv('CHARM_HOME', '.')

    generator = CharmGenerator(args)
    try:
        generator.create_charm()
    except CharmGeneratorException as e:
        log.error(e)
        return 1


class BashCharm(CharmTemplate):
    def create_charm(self, config, output_dir):
        home = path.abspath(path.dirname(__file__))
        template_dir = path.join(home, 'templates')
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(path.join(template_dir, 'charm'), output_dir)

        ignore_parsing = ['README.ex']

        for root, dirs, files in os.walk(output_dir):
            for outfile in files:
                full_outfile = path.join(root, outfile)
                mode = os.stat(full_outfile)[ST_MODE]
                if outfile in ignore_parsing:
                    continue

                try:
                    t = Template(file=full_outfile, searchList=(config))
                    o = tempfile.NamedTemporaryFile(dir=root, delete=False)
                    os.chmod(o.name, mode)
                    o.write(str(t))
                    o.close()
                    backupname = full_outfile + str(time.time())
                    os.rename(full_outfile, backupname)
                    try:
                        os.rename(o.name, full_outfile)
                        os.unlink(backupname)
                    except Exception, e:
                        print("WARNING: Could not enable templated file: " +
                              str(e))
                        os.rename(backupname, full_outfile)
                        raise
                except Exception, e:
                    print("WARNING: could not process template for " +
                          full_outfile + ": " + str(e))
                    raise


if __name__ == "__main__":
    sys.exit(main())
