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

from mock import patch, MagicMock
from os.path import join
from unittest import TestCase

import pkg_resources
import yaml

from charmtools.create import (
    apt_fill,
    main,
    portable_get_maintainer,
    setup_parser,
)


def flatten(path):
    for root, dirs, files in os.walk(path):
        for f in sorted(files):
            yield join(root[len(path):], f).lstrip('/')


class CreateTest(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @patch('charmtools.create.setup_parser')
    def test_main(self, setup_parser):
        """Functional test of a full 'charm create' run."""
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir

        setup_parser.return_value.parse_args.return_value = args

        main()

        outputdir = join(self.tempdir, args.charmname)
        actual_files = list(flatten(outputdir))
        expected_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/charm')))
        metadata = yaml.load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)

    @patch('charmtools.create.setup_parser')
    def test_charmhome_from_environ(self, setup_parser):
        class args(object):
            charmname = 'testcharm'
            charmhome = None

        setup_parser.return_value.parse_args.return_value = args

        with patch.dict('os.environ', {'CHARM_HOME': self.tempdir}):
            main()

        outputdir = join(self.tempdir, args.charmname)
        actual_files = list(flatten(outputdir))
        expected_files = list(flatten(pkg_resources.resource_filename(
            'charmtools', 'templates/charm')))
        metadata = yaml.load(open(join(outputdir, 'metadata.yaml'), 'r'))

        self.assertEqual(expected_files, actual_files)
        self.assertEqual(metadata['name'], args.charmname)

    @patch('charmtools.create.setup_parser')
    def test_dest_dir_exists(self, setup_parser):
        class args(object):
            charmname = 'testcharm'
            charmhome = self.tempdir

        setup_parser.return_value.parse_args.return_value = args
        os.mkdir(join(self.tempdir, args.charmname))

        self.assertEqual(1, main())


class ParserTest(TestCase):
    def test_parser(self):
        p = setup_parser()
        args = p.parse_args(['testcharm', '/tmp/testcharm'])

        self.assertEqual(args.charmname, 'testcharm')
        self.assertEqual(args.charmhome, '/tmp/testcharm')


class AptFillTest(TestCase):
    def _mock_apt(self, apt_mock):
        modules = {'apt': apt_mock}

        self.module_patcher = patch.dict('sys.modules', modules)
        self.module_patcher.start()

        self.addCleanup(self.module_patcher.stop)

    def test_known_package(self):
        apt = MagicMock()

        class pkg(object):
            summary = 'summary'
            description = 'description'

        cache = apt.Cache.return_value
        cache.__getitem__.return_value = pkg
        self._mock_apt(apt)

        d = apt_fill('python-apt')

        self.assertEqual(d['summary'], 'summary')
        self.assertEqual(d['description'], 'description')

    def test_known_package_new_apt(self):
        """Test python-apt >= 0.7.9"""
        apt = MagicMock()

        class pkg(object):
            class version(object):
                summary = 'summary'
                description = 'description'
            versions = [version]

        cache = apt.Cache.return_value
        cache.__getitem__.return_value = pkg
        self._mock_apt(apt)

        d = apt_fill('python-apt')

        self.assertEqual(d['summary'], 'summary')
        self.assertEqual(d['description'], 'description')

    def test_unknown_package(self):
        d = apt_fill('myfakepackage')

        self.assertEqual(d['summary'], '<Fill in summary here>')
        self.assertEqual(d['description'], '<Multi-line description here>')


class GetMaintainerTest(TestCase):
    @patch.dict('os.environ', {'NAME': 'Tester', 'EMAIL': 'test@example.com'})
    def test_from_environ(self):
        name, email = portable_get_maintainer()

        self.assertEqual(name, 'Tester')
        self.assertEqual(email, 'test@example.com')

    @patch('charmtools.create.socket')
    def test_no_pwd(self, socket):
        self.module_patcher = patch.dict('sys.modules', {'pwd': None})
        self.module_patcher.start()
        self.addCleanup(self.module_patcher.stop)

        socket.getfqdn.return_value = 'example.com'

        with patch.dict('os.environ', {}, clear=True):
            name, email = portable_get_maintainer()

        self.assertEqual(name, 'Your Name')
        self.assertEqual(email, 'Your.Name@example.com')

    @patch.dict('os.environ', {'EMAIL': 'test@example.com'})
    def test_pwd_name(self):
        pwd = MagicMock()
        pwd.getpwuid.return_value.pw_gecos = 'John Doe'

        self.module_patcher = patch.dict('sys.modules', {'pwd': pwd})
        self.module_patcher.start()
        self.addCleanup(self.module_patcher.stop)

        name, email = portable_get_maintainer()

        self.assertEqual(name, 'John Doe')
        self.assertEqual(email, 'test@example.com')

    @patch.dict('os.environ', {'EMAIL': 'test@example.com'})
    def test_pwd_empty_name(self):
        pwd = MagicMock()
        pwd.getpwuid.return_value.pw_gecos = ''
        pwd.getpwuid.return_value.__getitem__.return_value = 'jdoe'

        self.module_patcher = patch.dict('sys.modules', {'pwd': pwd})
        self.module_patcher.start()
        self.addCleanup(self.module_patcher.stop)

        name, email = portable_get_maintainer()

        self.assertEqual(name, 'jdoe')
        self.assertEqual(email, 'test@example.com')

    @patch.dict('os.environ', {'EMAIL': 'test@example.com'})
    def test_pwd_empty_username(self):
        pwd = MagicMock()
        pwd.getpwuid.return_value.pw_gecos = ''
        pwd.getpwuid.return_value.__getitem__.return_value = ''

        self.module_patcher = patch.dict('sys.modules', {'pwd': pwd})
        self.module_patcher.start()
        self.addCleanup(self.module_patcher.stop)

        name, email = portable_get_maintainer()

        self.assertEqual(name, 'Your Name')
        self.assertEqual(email, 'test@example.com')
