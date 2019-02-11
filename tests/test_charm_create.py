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

from mock import patch
from os.path import join
from unittest import TestCase

import pkg_resources
import yaml

from charmtools.create import (
    main,
    setup_parser,
)


def flatten(path):
    for root, dirs, files in os.walk(path):
        for f in sorted(files):
            yield join(root[len(path):], f).lstrip('/')


class BashCreateTest(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @patch('charmtools.generators.generator.log')
    @patch('charmtools.create.log')
    @patch('charmtools.create.setup_parser')
    def test_main(self, setup_parser, mlog, mglog):
        """Functional test of a full 'charm create' run."""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'bash'
            verbose = False

        setup_parser.return_value.parse_args.return_value = args

        unwriteable = join(self.tempdir, '_unwriteable')
        os.mkdir(unwriteable, 0o555)
        args.charmhome = unwriteable
        self.assertEqual(main(), 1)
        assert mlog.error.called
        self.assertIn('Unable to write to', mlog.error.call_args[0][0])

        mglog.warn.reset_mock()
        self.assertEqual(main(), 1)

        args.charmhome = self.tempdir
        self.assertEqual(main(), 0)

        outputdir = join(self.tempdir, args.charmname)
        actual_files = list(flatten(outputdir))
        expected_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/bash/files')))
        metadata = yaml.safe_load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)

    @patch('charmtools.create.setup_parser')
    def test_charmhome_from_environ(self, setup_parser):
        class args(object):
            charmname = 'testcharm'
            charmhome = None
            template = 'bash'
            verbose = False

        setup_parser.return_value.parse_args.return_value = args

        with patch.dict('os.environ', {'CHARM_HOME': self.tempdir,
                                       'USER': 'test'}):
            with patch('os.path.expanduser') as eu:
                eu.return_value = self.tempdir
                self.assertEqual(main(), 0)

        outputdir = join(self.tempdir, args.charmname)
        actual_files = list(flatten(outputdir))
        expected_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/bash/files')))
        metadata = yaml.safe_load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)

    @patch('charmtools.create.setup_parser')
    def test_dest_dir_exists(self, setup_parser):
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir
            template = 'bash'
            verbose = False

        setup_parser.return_value.parse_args.return_value = args
        os.mkdir(join(self.tempdir, args.charmname))

        with patch.dict('os.environ', {'USER': 'test'}):
            with patch('os.path.expanduser') as eu:
                eu.return_value = self.tempdir
                self.assertEqual(1, main())


class ParserTest(TestCase):
    def test_parser(self):
        p = setup_parser()
        args = p.parse_args(['testcharm', '/tmp/testcharm'])

        self.assertEqual(args.charmname, 'testcharm')
        self.assertEqual(args.charmhome, '/tmp/testcharm')
