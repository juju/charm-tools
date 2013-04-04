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
import bzrlib
import ConfigParser


class Mr:
    def __init__(self, directory=False, config=False, trust_all=False):
        self.directory = directory or os.getcwd()
        self.trust_all = trust_all
        self.config_file = config or os.path.join(self.directory, '.mrconfig')

        if self.check_mr_bzr_exists():
            if not config or not os.path.exists(config):
                raise Exception('No .mrconfig specified')
            cp = ConfigParser.ConfigParser()
            self.config = ConfigParser.read(config)
        else:
            self.config = ConfigParser.RawConfigParser()

    def update(self):
        print "Not today"

    # This isn't a true conversion of Mr, as such it's highly specialized
    # for just Charm Tools. So when you "add" a charm, it's just going
    # to use the charm name to fill in a template. Repository is in there
    # just in case we later add personal branching.
    def add(self, name=False, repository='lp:charms'):
        if not name raise Exception('No name provided')

    def remove(self, name=False):
        if not name raise Exception('No name provided')

    def check_mr_bzr_exists(self):
        return os.path.exists(os.path.join(self.directory, '.bzr'))
