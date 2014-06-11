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

import sys

from os.path import abspath, dirname, join
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent
from unittest import main, TestCase
from mock import Mock

proof_path = dirname(dirname(dirname(abspath(__file__))))
proof_path = join(proof_path, 'charmtools')

sys.path.append(proof_path)

from charmtools.charms import CharmLinter as Linter
from charmtools.charms import validate_maintainer


class TestCharmProof(TestCase):
    def setUp(self):
        self.charm_dir = mkdtemp()
        self.linter = Linter()

    def tearDown(self):
        rmtree(self.charm_dir)

    def write_config(self, text):
        with open(join(self.charm_dir, 'config.yaml'), 'w') as f:
            f.write(dedent(text))

    def test_config_yaml_missing(self):
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(
            ['I: File config.yaml not found.'], self.linter.lint)

    def test_clean_config(self):
        self.write_config("""
            options:
              string_opt:
                type: string
                description: A string option
                default: some text
              int_opt:
                type: int
                description: An int option
                default: 2
              float_opt:
                type: float
                default: 4.2
                description: This is a float option.
              bool_opt:
                type: boolean
                default: True
                description: This is a boolean option.
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual([], self.linter.lint)

    def test_missing_type_defaults_to_string(self):
        # A warning is issued but no failure.
        self.write_config("""
            options:
              string_opt:
                description: A string option
                default: some text
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(
            ['W: config.yaml: option string_opt does not have the keys: '
             'type'],
            self.linter.lint)

    def test_config_with_invalid_yaml(self):
        self.write_config("""
            options:
              foo: 42
              bar
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        message = self.linter.lint[0]
        self.assertTrue(message.startswith(
            'E: Cannot parse config.yaml: while scanning a simple key'),
            'wrong lint message: %s' % message)

    def test_config_no_root_dict(self):
        self.write_config("""
            this is not a dictionary
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        self.assertEqual(
            'E: config.yaml not parsed into a dictionary.',
            self.linter.lint[0])

    def test_options_key_missing(self):
        self.write_config("""
            foo: bar
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        self.assertEqual(
            'E: config.yaml must have an "options" key.',
            self.linter.lint[0])

    def test_ignored_root_keys(self):
        self.write_config("""
            options:
              string_opt:
                type: string
                description: whatever
                default: blah
            noise: The art of - in visible silence
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        self.assertEqual(
            "W: Ignored keys in config.yaml: ['noise']",
            self.linter.lint[0])

    def test_options_is_not_dict(self):
        self.write_config("""
            options: a string instead of a dict
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        self.assertEqual(
            'E: config.yaml: options section is not parsed as a dictionary',
            self.linter.lint[0])

    def test_option_data_not_a_dict(self):
        self.write_config("""
            options:
              foo: just a string
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        self.assertEqual(
            'E: config.yaml: data for option foo is not a dict',
            self.linter.lint[0])

    def test_option_data_with_subset_of_allowed_keys(self):
        self.write_config("""
            options:
              foo:
                type: int
                description: whatever
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: option foo does not have the keys: default')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_data_with_unknown_key(self):
        self.write_config("""
            options:
              foo:
                type: int
                default: 3
                description: whatever
                something: completely different
                42: the answer
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: option foo has unknown keys: 42, something')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_data_with_invalid_descr_type(self):
        self.write_config("""
            options:
              foo:
                type: int
                default: 3
                description: 1
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: description of option foo should be a non-empty string')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_data_with_blank_descr(self):
        self.write_config("""
            options:
              foo:
                type: int
                default: 3
                description:
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: description of option foo should be a non-empty string')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_data_with_missing_option_type(self):
        self.write_config("""
            options:
              foo:
                default: foo
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
                'W: config.yaml: option foo does not have the keys: type')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_data_with_invalid_option_type(self):
        self.write_config("""
            options:
              foo:
                type: strr
                default: foo
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: option foo has an invalid type (strr)')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_type_str_conflict_with_default_value(self):
        self.write_config("""
            options:
              foo:
                type: string
                default: 17
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'E: config.yaml: type of option foo is specified as string, but '
            'the type of the default value is int')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_type_int_conflict_with_default_value(self):
        self.write_config("""
            options:
              foo:
                type: int
                default: foo
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'E: config.yaml: type of option foo is specified as int, but '
            'the type of the default value is str')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_empty_default_value_string(self):
        # An empty default value is treated as INFO for strings
        self.write_config("""
            options:
              foo:
                type: string
                default:
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'I: config.yaml: option foo has no default value')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_empty_default_value_int(self):
        # An empty default value is treated as INFO for ints
        self.write_config("""
            options:
              foo:
                type: int
                default:
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'I: config.yaml: option foo has no default value')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_empty_default_value_float(self):
        # An empty default value is treated as INFO for floats
        self.write_config("""
            options:
              foo:
                type: float
                default:
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'I: config.yaml: option foo has no default value')
        self.assertEqual(expected, self.linter.lint[0])

    def test_option_empty_default_value_boolean(self):
        # An empty default value is treated as WARN for booleans
        self.write_config("""
            options:
              foo:
                type: boolean
                default:
                description: blah
            """)
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            'W: config.yaml: option foo has no default value')
        self.assertEqual(expected, self.linter.lint[0])

    def test_yaml_with_python_objects(self):
        """Python objects can't be loaded."""
        # Try to load the YAML representation of the int() function.
        self.write_config("!!python/name:__builtin__.int ''\n")
        self.linter.check_config_file(self.charm_dir)
        self.assertEqual(1, len(self.linter.lint))
        expected = (
            "E: Cannot parse config.yaml: could not determine a constructor "
            "for the tag 'tag:yaml.org,2002:python/name:__builtin__.int'")
        self.assertTrue(self.linter.lint[0].startswith(expected))


class MaintainerValidationTest(TestCase):
    def test_two_maintainer_fields(self):
        """Charm has maintainer AND maintainers."""
        linter = Mock()
        charm = {
            'maintainer': 'Tester <tester@example.com>',
            'maintainers': ['Tester <tester@example.com>'],
        }
        validate_maintainer(charm, linter)
        linter.err.assert_called_once_with(
            'Charm must not have both maintainer and maintainers fields')

    def test_no_maintainer_fields(self):
        """Charm has neither maintainer nor maintainers field."""
        linter = Mock()
        charm = {}
        validate_maintainer(charm, linter)
        linter.err.assert_called_once_with(
            'Charm must have either a maintainer or maintainers field')

    def test_maintainers_not_list(self):
        """Error if maintainers field is NOT a list."""
        linter = Mock()
        charm = {
            'maintainers': 'Tester <tester@example.com>',
        }
        validate_maintainer(charm, linter)
        linter.err.assert_called_once_with(
            'Maintainers field must be a list')

    def test_maintainer_list(self):
        """Error if maintainer field IS a list."""
        linter = Mock()
        charm = {
            'maintainer': ['Tester <tester@example.com>'],
        }
        validate_maintainer(charm, linter)
        linter.err.assert_called_once_with(
            'Maintainer field must not be a list')

    def test_maintainer_bad_format(self):
        """Warn if format of maintainer string not RFC2822 compliant."""
        linter = Mock()
        charm = {
            'maintainer': 'Tester tester@example.com',
        }
        validate_maintainer(charm, linter)
        linter.warn.assert_called_once_with(
            'Maintainer format should be "Name <Email>", not '
            '"Testertester@example.com"')
        self.assertFalse(linter.err.called)

    def test_maintainers_bad_format(self):
        """Warn if format of a maintainers string not RFC2822 compliant."""
        linter = Mock()
        charm = {
            'maintainers': ['Tester tester@example.com'],
        }
        validate_maintainer(charm, linter)
        linter.warn.assert_called_once_with(
            'Maintainer format should be "Name <Email>", not '
            '"Testertester@example.com"')
        self.assertFalse(linter.err.called)

    def test_good_maintainer(self):
        """Maintainer field happy path."""
        linter = Mock()
        charm = {
            'maintainer': 'Tester <tester@example.com>',
        }
        validate_maintainer(charm, linter)
        self.assertFalse(linter.err.called)
        self.assertFalse(linter.warn.called)

    def test_good_maintainers(self):
        """Maintainers field happy path."""
        linter = Mock()
        charm = {
            'maintainers': ['Tester <tester@example.com>'],
        }
        validate_maintainer(charm, linter)
        self.assertFalse(linter.err.called)
        self.assertFalse(linter.warn.called)


if __name__ == '__main__':
    main()
