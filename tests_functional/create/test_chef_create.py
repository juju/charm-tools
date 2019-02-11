#!/usr/bin/python

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

import os
import shutil
import tempfile
import unittest

from mock import patch
from os.path import join
from unittest import TestCase

import yaml

from charmtools.create import (
    main,
)


def flatten(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            yield join(root[len(path):], f).lstrip('/')


class ChefCreateTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _expected_files(self):
        static_files = [
            'hooks/config-changed',
            'hooks/install',
            'hooks/start',
            'hooks/stop',
            'hooks/stub',
            'cookbooks/Gemfile',
            'cookbooks/Gemfile.lock',
            'hooks/bootstrap',
            'hooks/upgrade-charm',
            'hooks/relation-name-relation-broken',
            'hooks/relation-name-relation-changed',
            'hooks/relation-name-relation-departed',
            'hooks/relation-name-relation-joined',
            'cookbooks/testcharm/metadata.rb',
            'cookbooks/testcharm/recipes/config-changed.rb',
            'cookbooks/testcharm/recipes/install.rb',
            'cookbooks/testcharm/recipes/start.rb',
            'cookbooks/testcharm/recipes/stop.rb',
            'cookbooks/testcharm/recipes/upgrade-charm.rb',
            'cookbooks/juju-helpers/definitions/juju_port.rb',
            'cookbooks/juju-helpers/definitions/relation_set.rb',
            'cookbooks/juju-helpers/libraries/juju.rb',
            'cookbooks/juju-helpers/libraries/juju/juju_helpers_dev.rb',
            'cookbooks/juju-helpers/libraries/juju/juju_helpers.rb',
            'cookbooks/juju-helpers/metadata.rb',
            'cookbooks/relation-name-relation/metadata.rb',
            'cookbooks/relation-name-relation/recipes/broken.rb',
            'cookbooks/relation-name-relation/recipes/changed.rb',
            'cookbooks/relation-name-relation/recipes/departed.rb',
            'cookbooks/relation-name-relation/recipes/joined.rb',
            'tests/00-setup',
            'tests/99-autogen',
            'icon.svg',
            'metadata.yaml',
            'README.ex',
            'config.yaml',
        ]
        return sorted(static_files)

    @patch('charmtools.create.setup_parser')
    def test_default(self, setup_parser):
        """Test of `charm create -t chef testcharm`"""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'chef'
            accept_defaults = True
            verbose = False

        setup_parser.return_value.parse_args.return_value = args

        main()

        outputdir = join(self.tempdir, args.charmname)
        actual_files = sorted(flatten(outputdir))
        expected_files = self._expected_files()
        metadata = yaml.safe_load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)


if __name__ == '__main__':
    unittest.main()
