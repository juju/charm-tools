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

from mock import Mock
from unittest import TestCase

from charmtools.generators import (
    CharmTemplate,
)


class CharmTemplateTest(TestCase):
    def test_create_charm(self):
        t = CharmTemplate()

        self.assertRaises(NotImplementedError, t.create_charm, {}, '.')

    def test_configure_prompt(self):
        t = CharmTemplate()
        prompt = Mock()

        self.assertEqual(prompt, t.configure_prompt(prompt, {}))

    def test_validate_input(self):
        t = CharmTemplate()
        prompt = Mock()
        t.validate_input('value', prompt, {})

        prompt.validate.assert_called_once_with('value')
