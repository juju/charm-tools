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

    def test_invalid_app_key(self):
        self.linter.validate({
            'invalid': {
                'memcached': {
                    'charm': 'cs:precise/memcached',
                    'num_units': 1,
                },
            }
        })
        self.assertIn(
            'E: No applications defined',
            self.linter.lint)

    def test_applications_warn_on_charm_urls_without_revisions(self):
        self.linter.validate({
            'applications': {
                'memcached': {
                    'charm': 'cs:precise/memcached',
                    'num_units': 1,
                },
            }
        })
        self.assertIn(
            'W: memcached: charm URL should include a revision',
            self.linter.lint)

    def test_services_warn_on_charm_urls_without_revisions(self):
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

    def test_hints_about_missing_display_name(self):
        self.linter.validate({
            'services': {
                'memcached': {
                    'charm': 'cs:precise/memcached',
                    'num_units': 1,
                },
            }
        })
        self.assertIn('I: `display-name` not provided, add for custom naming in the UI',
                      self.linter.lint)

    def test_allows_valid_display_name(self):
        # These names are copied from the juju/names package tests.
        # https://github.com/juju/names/blob/master/charm_test.go#L42
        valid_names = [
            'ABC',
            'My Awesome Charm',
            'my-charm-name',
            '1-abc-2',
            'underscores_allowed',
        ]
        for name in valid_names:
            self.linter.validate({'display-name': name})
            self.assertNotIn('E: display-name: not in valid format. '
                             'Only letters, numbers, dashes, and hyphens are permitted.',
                             self.linter.lint)

    def test_validates_display_name(self):
        # These names are copied from the juju/names package tests.
        # https://github.com/juju/names/blob/master/charm_test.go#L42
        invalid_names = [
            ' bad name',
            'big  space',
            'bigger    space',
            'tabs	not	allowed',
            'no\nnewlines',
            'no\r\nnewlines',
        ]
        for name in invalid_names:
            self.linter.validate({'display-name': name})
            self.assertIn('E: display-name: not in valid format. '
                          'Only letters, numbers, dashes, and hyphens are permitted.',
                          self.linter.lint)
