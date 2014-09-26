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
import shutil
import subprocess
import tempfile

from Cheetah.Template import Template
from stat import ST_MODE

from charmtools.generators import (
    CharmTemplate,
)

log = logging.getLogger(__name__)


class AnsibleCharmTemplate(CharmTemplate):
    skip_parsing = ['README.ex', 'Makefile']

    def create_charm(self, config, output_dir):
        self._copy_files(output_dir)

        for root, dirs, files in os.walk(output_dir):
            for outfile in files:
                if outfile in self.skip_parsing:
                    continue

                self._template_file(config, path.join(root, outfile))

        self._cleanup_hooks(config, output_dir)
        self._install_charmhelpers(output_dir)

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
        o.write(str(t))
        o.close()
        backupname = outfile + str(time.time())
        os.rename(outfile, backupname)
        os.rename(o.name, outfile)
        os.unlink(backupname)

    def _cleanup_hooks(self, config, output_dir):
        # Symlinks must be relative so that they are copied properly
        # when output_dir is moved to it's final location.
        for link in ['config-changed', 'install', 'start', 'stop',
                     'upgrade-charm']:
            os.symlink('hooks.py', os.path.join(output_dir, 'hooks', link))

    def _install_charmhelpers(self, output_dir):
        helpers_dest = os.path.join(output_dir, 'lib', 'charmhelpers')
        if not os.path.exists(helpers_dest):
            os.makedirs(helpers_dest)

        cmd = './scripts/charm_helpers_sync.py -c charm-helpers.yaml'
        subprocess.check_call(cmd.split(), cwd=output_dir)
