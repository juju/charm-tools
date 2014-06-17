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

from unittest import TestCase

from charmtools.generators import (
    Prompt,
    PromptList,
)


class PromptListTest(TestCase):
    def test_init_empty(self):
        self.assertEqual([], PromptList())

    def test_init_with_data(self):
        data = {
            'symlink': {
                'prompt': 'one file per hook?',
                'default': 'y',
                'type': 'bool',
            }
        }
        pl = PromptList(data)

        self.assertEqual(1, len(pl))
        self.assertIsInstance(pl[0], Prompt)


class PromptTest(TestCase):
    def test_init(self):
        p = Prompt('symlink', 'one file per hook?', 'y')

        self.assertEqual(p.name, 'symlink')
        self.assertEqual(p.prompt, 'one file per hook? ')
        self.assertEqual(p.default, 'y')
        self.assertEqual(p.type_, 'string')

    def test_validate_string(self):
        p1 = Prompt('name', 'your name?', 'Name', 'string')
        p2 = Prompt('name', 'your name?', 'Name', 'str')

        self.assertEqual('Joe', p1.validate('Joe'))
        self.assertEqual('Joe', p2.validate('Joe'))

    def test_validate_int(self):
        p1 = Prompt('age', 'your age?', '0', 'integer')
        p2 = Prompt('age', 'your age?', '0', 'int')

        self.assertEqual(18, p1.validate('18'))
        self.assertEqual(18, p2.validate('18'))

    def test_validate_float(self):
        p1 = Prompt('temp', 'temperature?', '0', 'float')

        self.assertEqual(98.6, p1.validate('98.6'))
        self.assertEqual(100.0, p1.validate('100'))

    def test_validate_bool(self):
        p1 = Prompt('symlink', 'one file per hook?', 'y', 'boolean')
        p2 = Prompt('symlink', 'one file per hook?', 'y', 'bool')

        self.assertTrue(p1.validate('True'))
        self.assertTrue(p1.validate('Yes'))
        self.assertTrue(p1.validate('y'))
        self.assertFalse(p2.validate('False'))
        self.assertFalse(p2.validate('No'))
        self.assertFalse(p2.validate('n'))
