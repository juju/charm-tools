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
import ConfigParser

from bzrlib.bzrdir import BzrDir


class Mr:
    def __init__(self, directory=False, config=False, trust_all=False):
        self.directory = directory or os.getcwd()
        self.control_dir = os.path.join(self.directory, '.bzr')
        self.trust_all = trust_all
        self.config_file = config or os.path.join(self.directory, '.mrconfig')

        if self._check_repository_exists():
            self.config = self._read_cfg()
            self.bzr_dir = BzrDir.open(self.directory)
        else:
            self.config = ConfigParser.RawConfigParser()
            self.bzr_dir = BzrDir.create(self.directory)
            self.bzr_dir.create_repository(shared=True)

    def update(self):
        pass

    def add(self, name=False, repository='lp:charms'):
        # This isn't a true conversion of Mr, as such it's highly specialized
        # for just Charm Tools. So when you "add" a charm, it's just going
        # to use the charm name to fill in a template. Repository is in there
        # just in case we later add personal branching.
        if not name:
            raise Exception('No name provided')
        if not self.config.has_section(name):
            self.config.add_section(name)

        self.config.set(name, 'checkout', os.path.join(repository, name))

    def checkout(self):
        pass

    def remove(self, name=False):
        if not name:
            raise Exception('No name provided')

        self.config.remove_section(name)

    def _write_cfg(self):
        pass

    def _read_cfg(self):
        if not self.config_file:
            raise Exception('No .mrconfig specified')
        return ConfigParser.read(self.config_file)

    def _check_repository_exists(self):
        # Eventually do more checks to make sure it is a shared repository
        # and not a branch, etc.
        return os.path.exists(self.control_dir)
