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

import pkg_resources
import yaml

from charmtools.create import (
    main,
)


def flatten(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            yield join(root[len(path):], f).lstrip('/')


class AnsibleCreateTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _expected_files(self):
        static_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/ansible/files')))
        dynamic_files = [
            'hooks/config-changed',
            'hooks/install',
            'hooks/start',
            'hooks/stop',
            'hooks/upgrade-charm',
            'lib/charmhelpers/__init__.py',
            'lib/charmhelpers/contrib/__init__.py',
            'lib/charmhelpers/contrib/ansible/__init__.py',
            'lib/charmhelpers/contrib/templating/__init__.py',
            'lib/charmhelpers/contrib/templating/contexts.py',
            'lib/charmhelpers/core/__init__.py',
            'lib/charmhelpers/core/decorators.py',
            'lib/charmhelpers/core/files.py',
            'lib/charmhelpers/core/fstab.py',
            'lib/charmhelpers/core/hookenv.py',
            'lib/charmhelpers/core/host.py',
            'lib/charmhelpers/core/hugepage.py',
            'lib/charmhelpers/core/kernel.py',
            'lib/charmhelpers/core/services/__init__.py',
            'lib/charmhelpers/core/services/base.py',
            'lib/charmhelpers/core/services/helpers.py',
            'lib/charmhelpers/core/strutils.py',
            'lib/charmhelpers/core/sysctl.py',
            'lib/charmhelpers/core/templating.py',
            'lib/charmhelpers/core/unitdata.py',
            'lib/charmhelpers/fetch/__init__.py',
            'lib/charmhelpers/fetch/archiveurl.py',
            'lib/charmhelpers/fetch/bzrurl.py',
            'lib/charmhelpers/fetch/giturl.py',
        ]
        return sorted(static_files + dynamic_files)

    @patch('charmtools.create.setup_parser')
    def test_default(self, setup_parser):
        """Test of `charm create -t ansible testcharm`"""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'ansible'
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
