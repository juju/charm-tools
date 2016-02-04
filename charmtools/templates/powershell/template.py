#!/usr/bin/python
#
#    Copyright (C) 2016  Canonical Ltd.
#    Copyright (C) 2016 Cloudbase Solutions SRL
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
import os.path as path
import shutil
import subprocess

from charmtools.generators import CharmTemplate


class PowerShellCharmTemplate(CharmTemplate):
    """ CharmTemplate specific to PowerShell charms. """

    # _EXTRA_FILES is the list of names of files present in the git repo
    # we don't want transferred over to the charm template:
    _EXTRA_FILES = ["README.md", ".git", ".gitmodules"]

    _TEMPLATE_URL = "https://github.com/cloudbase/windows-charms-boilerplate"

    def __init__(self):
        self.skip_parsing += ["*.ps1", "*.psm1"]

    def create_charm(self, config, output_dir):
        cmd = "git clone --recursive {} {}".format(
            self._TEMPLATE_URL, output_dir
        )

        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error has ocurred whilst attempting to clone"
                "the powershell charm template. Please make sure you have"
                "git installed on your system.\n" + e
            )

        # iterate and remove all the unwanted files from the git repo:
        for item in [path.join(output_dir, i) for i in self._EXTRA_FILES]:
            if not path.exists(item):
                continue

            if path.isdir(item) and not path.islink(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
