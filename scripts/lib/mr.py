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
        if not config or not os.path.exists(config):
            raise Exception('No .mrconfig specified')
        cp = ConfigParser.ConfigParser()
        self.config = ConfigParser.read(config)
        self.config_file = config


    def update(self):
        print "Not today"
