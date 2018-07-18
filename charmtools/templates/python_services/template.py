#!/usr/bin/python
#
#    Copyright (C) 2014  Canonical Ltd.
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
import sys
import shutil
import tempfile

from Cheetah.Template import Template
from stat import ST_MODE

from charmtools.generators import (
    CharmTemplate,
)

log = logging.getLogger(__name__)


class PythonServicesCharmTemplate(CharmTemplate):
    """Creates a python-based charm using the services framework"""

    def create_charm(self, config, output_dir):
        self._copy_files(output_dir)

        for root, dirs, files in os.walk(output_dir):
            for outfile in files:
                if self.skip_template(outfile):
                    continue

                self._template_file(config, path.join(root, outfile))

    def _copy_files(self, output_dir):
        here = path.abspath(path.dirname(__file__))
        template_dir = path.join(here, 'files')
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(template_dir, output_dir)

    def _template_file(self, config, outfile):
        if path.islink(outfile):
            return

        mode = os.stat(outfile)[ST_MODE]
        t = Template(file=outfile, searchList=(config))
        o = tempfile.NamedTemporaryFile(
            dir=path.dirname(outfile), delete=False)
        os.chmod(o.name, mode)
        st = str(t)
        if sys.version_info >= (3, ):
            st = st.encode('UTF-8')
        o.write(st)
        o.close()
        backupname = outfile + str(time.time())
        os.rename(outfile, backupname)
        os.rename(o.name, outfile)
        os.unlink(backupname)
