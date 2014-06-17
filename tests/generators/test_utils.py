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

from mock import patch, MagicMock
from unittest import TestCase

from charmtools.generators.utils import (
    apt_fill,
    portable_get_maintainer,
)


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

    @patch('charmtools.generators.utils.socket')
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
