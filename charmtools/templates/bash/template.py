#!/usr/bin/python
#
#    Copyright (C) 2014  Canonical Ltd.
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
import os.path as path
import time
import shutil
import tempfile

from Cheetah.Template import Template
from stat import ST_MODE

from charmtools.generators import CharmTemplate

log = logging.getLogger(__name__)


class BashCharmTemplate(CharmTemplate):
    def create_charm(self, config, output_dir):
        here = path.abspath(path.dirname(__file__))
        template_dir = path.join(here, 'files')
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(template_dir, output_dir)

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
