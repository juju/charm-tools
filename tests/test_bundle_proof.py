#!/usr/bin/python

#    Copyright (C) 2013  Canonical Ltd.
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

import charmtools.bundles
import unittest


class TestCharmProof(unittest.TestCase):
    def setUp(self):
        self.linter = charmtools.bundles.BundleLinter()

    def test_warn_on_charm_urls_without_revisions(self):
        self.linter.validate({
            'services': {
                'memcached': {
                    'charm': 'cs:precise/memcached',
                    'num_units': 1,
                },
            }
        })
        self.assertIn(
            'W: memcached: charm URL should include a revision',
            self.linter.lint)

    def test_no_warning_when_charm_urls_include_revisions(self):
        self.linter.validate({
            'services': {
                'memcached': {
                    'charm': 'cs:precise/memcached-99',
                    'num_units': 1,
                },
            }
        })
        self.assertNotIn(
            'W: memcached: charm URL should include a revision',
            self.linter.lint)

    def test_warn_on_missing_annotations(self):
        self.linter.validate({
            'services': {
                'memcached': {
                    'charm': 'cs:precise/memcached',
                    'num_units': 1,
                },
            }
        })
        self.assertIn(
            'W: memcached: No annotations found, will render '
            'poorly in GUI',
            self.linter.lint)

    def test_no_warning_when_annotations_are_included(self):
        self.linter.validate({
            'my-service': {
                'services': {
                    'memcached': {
                        'charm': 'cs:precise/memcached',
                        'num_units': 1,
                        'annotations': {
                            'gui-x': '821.5',
                            'gui-y': '669.2698359714502',
                        },
                    },
                },
            }})
        self.assertNotIn(
            'W: my-service: memcached: No annotations found, will render '
            'poorly in GUI',
            self.linter.lint)
