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

from bzrlib import trace
from bzrlib.bzrdir import BzrDir
from bzrlib.branch import Branch
from bzrlib.plugin import load_plugins
from bzrlib.repository import Repository

load_plugins()
trace.enable_default_logging()  # Provide better error handling


class Mr:
    def __init__(self, directory=None, config=None, mr_compat=True):
        self.directory = directory or os.getcwd()
        self.control_dir = os.path.join(self.directory, '.bzr')
        self.config_file = config or os.path.join(self.directory, '.mrconfig')
        self.mr_compat = mr_compat

        if mr_compat:
            if self.__is_repository():
                self.config = self.__read_cfg()
                self.bzr_dir = Repository.open(self.directory)
            else:
                self.config = ConfigParser.RawConfigParser()
                r = BzrDir.create(self.directory)
                self.bzr_dir = r.create_repository(shared=True)
        else:
            self.config = ConfigParser.RawConfigParser()
            self.bzr_dir = None

    def add(self, name, repository='lp:charms', checkout=False):
        # This isn't a true conversion of Mr, as such it's highly specialized
        # for just Charm Tools. So when you "add" a charm, it's just going
        # to use the charm name to fill in a template. Repository is in there
        # just in case we later add personal branching.
        '''Add a respository to the mrconfig'''
        if not name:
            raise Exception('No name provided')
        if not self.config.has_section(name):
            self.config.add_section(name)

        self.config.set(name, 'checkout', "bzr branch %s %s" %
                        (repository, name))

        if checkout:
            self.checkout(name)

    def checkout(self, name=None):
        '''Checkout either one or all repositories from the mrconfig'''
        if not name:
            for name in self.config.sections():
                charm_remote = self.__get_repository(name)
                self.__checkout(charm_remote,
                                os.path.join(self.directory, name))
        else:
            # Move this, and the charm_* stuff to _checkout? Makes sense
            if not self.config.has_section(name):
                raise Exception('No configuration for %s' % name)

            charm_remote = self.__get_repository(name)
            self.__checkout(charm_remote,
                            os.path.join(self.directory, name))

    def update(self, name=None, force=False):
        '''Update, or checkout, a charm in to directory'''
        if name:
            self.__update(name)
        else:
            for charm in self.config.sections():
                self.__update(charm)

    def remove(self, name=None):
        '''Remove a repository from the mrconfig'''
        if not name:
            raise Exception('No name provided')

        self.config.remove_section(name)

    def list(self):
        '''Return all sections of the mr configuration'''
        return self.config.sections()

    def exists(self, name):
        '''Checks if the configuration already exists for this section'''
        return self.config.has_section(name)

    def save(self):
        '''Save the configuration file to disk'''
        with open(self.config_file, 'w') as mrcfg:
            self.config.write(mrcfg)

    __write_cfg = save

    def __read_cfg(self):
        cfg = ConfigParser.ConfigParser()
        if not self.config_file:
            raise Exception('No .mrconfig specified')
        if os.path.exists(self.config_file):
            cfg.read(self.config_file)
        return cfg

    def __checkout(self, src, to):
        remote = Branch.open(src)
        remote.bzrdir.sprout(to)
        # I wish there was a way to 'close' a RemoteBranch. Sadly,
        # I don't think there is

    def __update(self, name):
        if not os.path.exists(os.path.join(self.directory, name, '.bzr')):
            return self.checkout(name)

        charm_remote = self.__get_repository(name)
        local_branch = Branch.open(os.path.join(self.directory, name))
        remote_branch = Branch.open(charm_remote)
        local_branch.pull(remote_branch)

    def __get_repository(self, name):
        if not self.config.has_section(name):
            raise Exception('No section "%s" configured' % name)

        return self.config.get(name, 'checkout').split(' ')[-2]

    def __is_repository(self):
        try:
            r = Repository.open(self.directory)
        except:
            return False

        return r.is_shared()
