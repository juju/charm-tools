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
import six
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


if six.PY3:
    _builtins_raw_input = "builtins.input"
else:
    _builtins_raw_input = "__builtin__.raw_input"


def flatten(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            yield join(root[len(path):], f).lstrip('/')


class PythonBasicCreateTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _expected_files(self):
        static_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/python/files')))
        dynamic_files = [
            'lib/charmhelpers/__init__.py',
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
        ]
        return sorted(static_files + dynamic_files)

    @patch('charmtools.create.setup_parser')
    def test_defaults(self, setup_parser):
        """Functional test of a full 'charm create' run."""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'python-basic'
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


class PythonServicesCreateTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _expected_files(self):
        static_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/python_services/files')))
        return sorted(static_files)

    @patch(_builtins_raw_input)
    @patch('charmtools.create.setup_parser')
    def test_interactive(self, setup_parser, raw_input_):
        """Functional test of a full 'charm create' run."""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'python'
            accept_defaults = False
            verbose = False

        setup_parser.return_value.parse_args.return_value = args
        raw_input_.side_effect = ['Y']

        main()

        outputdir = join(self.tempdir, args.charmname)
        actual_files = sorted(flatten(outputdir))
        expected_files = self._expected_files()
        metadata = yaml.safe_load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)

    @patch('charmtools.create.setup_parser')
    def test_defaults(self, setup_parser):
        """Functional test of a full 'charm create' run."""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'python'
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
