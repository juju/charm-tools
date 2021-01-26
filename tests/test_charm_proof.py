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
import yaml

from os.path import abspath, dirname, join
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent
from unittest import main, TestCase
from mock import Mock, call, patch

proof_path = dirname(dirname(dirname(abspath(__file__))))
proof_path = join(proof_path, 'charmtools')

sys.path.append(proof_path)

from charmtools.charms import CharmLinter as Linter  # noqa
from charmtools.charms import Charm  # noqa
from charmtools.charms import validate_display_name  # noqa
from charmtools.charms import validate_maintainer  # noqa
from charmtools.charms import validate_categories_and_tags  # noqa
from charmtools.charms import validate_storage  # noqa
from charmtools.charms import validate_devices  # noqa
from charmtools.charms import validate_series  # noqa
from charmtools.charms import validate_min_juju_version  # noqa
from charmtools.charms import validate_extra_bindings  # noqa
from charmtools.charms import validate_payloads  # noqa
from charmtools.charms import validate_actions  # noqa
from charmtools.charms import validate_functions  # noqa
from charmtools.charms import validate_terms  # noqa
from charmtools.charms import validate_resources  # noqa
from charmtools.charms import validate_deployment  # noqa
from charmtools.charms import validate_metadata_keys  # noqa


class TestCharmProof(TestCase):
    def setUp(self):
        self.charm_dir = mkdtemp()
        self.linter = Linter()

    def tearDown(self):
        rmtree(self.charm_dir)

    def write_config(self, text):
        with open(join(self.charm_dir, 'config.yaml'), 'w') as f:
            f.write(dedent(text))

    def write_metadata(self, text):
        with open(join(self.charm_dir, 'metadata.yaml'), 'w') as f:
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
        expected = ('W: config.yaml: description of option '
                    'foo should be a non-empty string')
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
        expected = ('W: config.yaml: description of option '
                    'foo should be a non-empty string')
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
            'I: config.yaml: option foo has no default value')
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

    def test_valid_layer_yaml(self):
        self.write_metadata("{}")
        with open(join(self.charm_dir, 'layer.yaml'), 'w') as f:
            f.write("valid: {}")
        with patch.object(Charm, 'is_charm'):
            charm = Charm(self.charm_dir, self.linter)
        charm.proof()
        assert not any(msg.startswith('W: cannot parse {}/layer.yaml: '
                                      ''.format(self.charm_dir))
                       for msg in self.linter.lint)

    def test_invalid_layer_yaml(self):
        self.write_metadata("{}")
        with open(join(self.charm_dir, 'layer.yaml'), 'w') as f:
            f.write("invalid: {")
        Charm(self.charm_dir, self.linter).proof()
        assert any(msg.startswith('W: cannot parse {}/layer.yaml: '
                                  ''.format(self.charm_dir))
                   for msg in self.linter.lint)

    def test_load_proof_extensions(self):
        mocks = {
            'validate_storage': None,
            'validate_devices': None,
            'validate_resources': None,
            'validate_payloads': None,
        }
        for validator in mocks.keys():
            patcher = patch('charmtools.charms.{}'.format(validator))
            mocks[validator] = patcher.start()
            self.addCleanup(patcher.stop)
        self.write_metadata("{}")
        with open(join(self.charm_dir, 'layer.yaml'), 'w') as f:
            f.write(dedent("""
                           proof:
                             storage:
                               - name: ext
                                 type: Boolean
                             devices:
                               - name: ext
                                 type: Boolean
                             resources:
                               - name: ext
                                 type: Boolean
                             payloads:
                               - name: ext
                                 type: Boolean
                           """))
        charm = Charm(self.charm_dir, self.linter)
        charm.proof()
        for mock in mocks.values():
            mock.assert_called_once_with({},
                                         self.linter,
                                         [{'name': 'ext',
                                           'type': 'Boolean'}])

    def test_metadata_clean(self):
        self.write_metadata("""
            name: test
            summary: test charm
            """)
        with open(join(self.charm_dir, 'metadata.yaml'), 'rb') as metadata_yaml:
            charm = yaml.safe_load(metadata_yaml)
        validate_metadata_keys(charm, self.linter)
        self.assertEqual([], self.linter.lint)

    def test_metadata_missing_key(self):
        self.write_metadata("""
            name: test
            """)
        with open(join(self.charm_dir, 'metadata.yaml'), 'rb') as metadata_yaml:
            charm = yaml.safe_load(metadata_yaml)
        validate_metadata_keys(charm, self.linter)
        self.assertEqual(["E: Missing required metadata field (summary)"], self.linter.lint)

    def test_metadata_unknown_key(self):
        self.write_metadata("""
            name: test
            summary: test charm
            fake: this should warn
            """)
        with open(join(self.charm_dir, 'metadata.yaml'), 'rb') as metadata_yaml:
            charm = yaml.safe_load(metadata_yaml)
        validate_metadata_keys(charm, self.linter)
        self.assertEqual(["I: Unknown root metadata field (fake)"], self.linter.lint)


class CategoriesTagsValidationTest(TestCase):
    def test_no_categories_or_tags(self):
        """Charm has neither categories nor tags."""
        linter = Mock()
        charm = {}
        validate_categories_and_tags(charm, linter)
        linter.warn.assert_called_once_with(
            'Metadata missing required field "tags"')

    def test_invalid_tags(self):
        """Charm has invalid tags field"""
        warning = 'Metadata field "tags" must be a non-empty list'
        linter = Mock()
        validate_categories_and_tags({'tags': 'foo'}, linter)
        linter.warn.assert_called_once_with(warning)
        linter.reset_mock()
        validate_categories_and_tags({'tags': []}, linter)
        linter.warn.assert_called_once_with(warning)

    def test_invalid_categories(self):
        """Charm has invalid categories field"""
        warning = (
            'Categories metadata must be a list of one or more of: '
            'applications, app-servers, databases, file-servers, '
            'cache-proxy, misc'
        )
        linter = Mock()
        validate_categories_and_tags({'categories': 'foo'}, linter)
        linter.warn.assert_any_call(warning)
        linter.reset_mock()
        validate_categories_and_tags({'categories': []}, linter)
        linter.warn.assert_any_call(warning)

    def test_valid_categories(self):
        """Charm has valid categories, which should be changed to tags"""
        info = (
            'Categories are being deprecated in favor of tags. '
            'Please rename the "categories" field to "tags".'
        )
        linter = Mock()
        validate_categories_and_tags({'categories': ['misc']}, linter)
        linter.warn.assert_called_once_with(info)
        self.assertFalse(linter.info.called)
        self.assertFalse(linter.err.called)


class DisplayNameValidationTest(TestCase):
    def test_educates_display_name(self):
        """Charm does not have a display_name."""
        linter = Mock()
        charm = {
            'name': 'peanutbutter'
        }
        validate_display_name(charm, linter)
        linter.info.assert_called_once_with(
            '`display-name` not provided, add for custom naming in the UI')

    def test_allows_display_name(self):
        """Charm has a display_name."""
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
            linter = Mock()
            charm = {
                'display-name': name
            }
            validate_display_name(charm, linter)
            linter.info.assert_not_called()
            linter.err.assert_not_called()
            linter.warn.assert_not_called()

    def test_display_name_alphanumeric_only(self):
        """Charm had invalid display_name."""
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
            linter = Mock()
            charm = {
                'display-name': name
            }
            validate_display_name(charm, linter)
            linter.err.assert_called_once_with(
                'display-name: not in valid format. Only letters, numbers, '
                'dashes, and hyphens are permitted.'
            )


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
            '"Tester tester@example.com"')
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
            '"Tester tester@example.com"')
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
            'maintainers': [
                'Tester <tester@example.com>',
                'Tester Joe H. <tester@example.com>',
            ]
        }
        validate_maintainer(charm, linter)
        self.assertFalse(linter.err.called)
        self.assertFalse(linter.warn.called, "linter.warn was called, sadly")


class DevicesValidationTest(TestCase):
    def test_minimal_devices_config(self):
        """Charm has the minimum allowed devices configuration."""
        linter = Mock()
        charm = {
            'devices': {
                'bitcoinminer': {
                    'type': 'nvidia.com/gpu',
                    'count': 1
                }
            }
        }
        validate_devices(charm, linter)
        self.assertFalse(linter.err.called)

    def test_devices_with_invalid_config(self):
        """Charm has empty devices configuration."""
        linter = Mock()
        charm = {
            'devices': 'invalid devices config'
        }
        validate_devices(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('devices: must be a dictionary of device definitions'),
        ], any_order=True)

    def test_devices_with_invalid_values(self):
        """Charm has devices with invalid values."""
        linter = Mock()
        charm = {
            'devices': {
                'bitcoinminer': {
                    'type': 'nvidia.com/gpu',
                    'count': 'non number'
                },
                'bitcoinminer1': {
                    'count': 1
                }
            }
        }
        validate_devices(charm, linter)
        self.assertEqual(linter.err.call_count, 2)
        linter.err.assert_has_calls([
            call('devices.bitcoinminer.count: "non number" is not a number'),
            call('devices.bitcoinminer1.type: Required'),
        ], any_order=True)

    def test_devices_unknown_keys(self):
        """Charm has devices with illegal keys."""
        linter = Mock()
        charm = {
            'devices': {
                'bitcoinminer': {
                    'type': 'nvidia.com/gpu',
                    'count': 1,
                    'unknown': True
                }
            }
        }
        validate_devices(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('devices.bitcoinminer: Unrecognized keys in mapping: '
                 '"{\'unknown\': True}"'),
        ], any_order=True)

    def test_devices_proof_extensions(self):
        """Charm has devices with proof extensions."""
        linter = Mock()
        charm = {
            'devices': {
                'bitcoinminer': {
                    'type': 'nvidia.com/gpu',
                    'count': 1,
                    'unknown': True
                }
            }
        }
        extensions = [
            {
                'name': 'unknown',
                'type': 'Boolean',
            }
        ]
        validate_devices(charm, linter, extensions)
        self.assertEqual(linter.err.call_args_list, [])


class StorageValidationTest(TestCase):
    def test_minimal_storage_config(self):
        """Charm has the minimum allowed storage configuration."""
        linter = Mock()
        charm = {
            'storage': {
                'data': {
                    'type': 'filesystem',
                }
            }
        }
        validate_storage(charm, linter)
        self.assertFalse(linter.err.called)

    def test_complete_storage_config(self):
        """Charm has a storage configuration using all options."""
        linter = Mock()
        charm = {
            'storage': {
                'data': {
                    'type': 'filesystem',
                    'description': 'my storage',
                    'shared': False,
                    'read-only': 'true',
                    'minimum-size': '10G',
                    'location': '/srv/data',
                },
                'disks': {
                    'type': 'block',
                    'multiple': {
                        'range': '10-'
                    }
                }
            }
        }
        validate_storage(charm, linter)
        self.assertFalse(linter.err.called)

    def test_storage_without_defs(self):
        """Charm has storage key but no storage definitions."""
        linter = Mock()
        charm = {
            'storage': {}
        }
        validate_storage(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('storage: must be a dictionary of storage definitions'),
        ], any_order=True)

    def test_storage_invalid_values(self):
        """Charm has storage with invalid values."""
        linter = Mock()
        charm = {
            'storage': {
                'data': {
                    'type': 'unknown',
                    'shared': 'maybe',
                    'read-only': 'no',
                    'minimum-size': '10k',
                },
                'disks': {
                    'type': 'block',
                    'multiple': {
                        'range': '10+'
                    }
                }
            }
        }
        validate_storage(charm, linter)
        self.assertEqual(linter.err.call_count, 5)
        linter.err.assert_has_calls([
            call('storage.data.type: "unknown" is not one of '
                 'filesystem, block'),
            call('storage.data.shared: "maybe" is not one of true, false'),
            call('storage.data.read-only: "no" is not one of true, false'),
            call('storage.data.minimum-size: must be a number followed by '
                 'an optional M/G/T/P, e.g. 100M'),
            call('storage.disks.multiple.range: supported formats are: '
                 'm (a fixed number), m-n (an explicit range), and '
                 'm- (a minimum number)'),
        ], any_order=True)

    def test_storage_unknown_keys(self):
        """Charm has storage with illegal keys."""
        linter = Mock()
        charm = {
            'storage': {
                'data': {
                    'type': 'filesystem',
                    'unknown': 'invalid key',
                },
            }
        }
        validate_storage(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('storage.data: Unrecognized keys in mapping: '
                 '"{\'unknown\': \'invalid key\'}"'),
        ], any_order=True)

    def test_storage_proof_extensions(self):
        """Charm has storage with proof extensions."""
        linter = Mock()
        charm = {
            'storage': {
                'data': {
                    'type': 'filesystem',
                    'unknown': 'invalid key',
                },
            }
        }
        extensions = [
            {
                'name': 'unknown',
                'type': 'String',
            }
        ]
        validate_storage(charm, linter, extensions)
        self.assertEqual(linter.err.call_args_list, [])


class DeploymentValidationTest(TestCase):
    def test_deployment(self):
        """Charm has valid deployment."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'stateful',
                'service': 'omit',
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertFalse(linter.err.called)

    def test_deployment_type_optional(self):
        """Charm has valid deployment with empty type."""
        linter = Mock()
        charm = {
            'deployment': {
                'service': 'omit',
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertFalse(linter.err.called)

    def test_invalid_deployment(self):
        """Charm has invalid deployment."""
        linter = Mock()
        charm = {
            'deployment': [],
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('deployment: must be a dict of config'),
        ], any_order=True)

    def test_deployment_unsupported_field(self):
        """Charm has the invalid deployment field."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'stateful',
                'service': 'omit',
                'min-version': "1.15.0",
                'unknow-field': 'xxx',
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('deployment.deployment: Unrecognized keys in mapping: "{\'unknow-field\': \'xxx\'}"'),
        ], any_order=True)
        

    def test_deployment_invalid_type(self):
        """Charm has the invalid deployment type."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': True,
                'service': 'omit',
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call("deployment.deployment.type: True is not a string: {'type': ''}"),
        ], any_order=True)

    def test_deployment_unsupported_type(self):
        """Charm has the unsupported deployment type."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'foo',
                'service': 'omit',
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('deployment.deployment.type: "foo" is not one of stateless, stateful, daemon'),
        ], any_order=True)

    def test_deployment_invalid_service(self):
        """Charm has the invalid deployment service."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'stateful',
                'service': 1,
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call("deployment.deployment.service: 1 is not a string: {'service': ''}"),
        ], any_order=True)

    def test_deployment_unsupported_service(self):
        """Charm has the unsupported deployment service."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'stateful',
                'service': 'foo',
                'min-version': "1.15.0",
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('deployment.deployment.service: "foo" is not one of loadbalancer, cluster, omit'),
        ], any_order=True)

    def test_deployment_invalid_min_version(self):
        """Charm has the invalid deployment min-version."""
        linter = Mock()
        charm = {
            'deployment': {
                'type': 'stateful',
                'service': 'omit',
                'min-version': 1.15,
            }
        }
        validate_deployment(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call("deployment.deployment.min-version: 1.15 is not a string: {'min-version': ''}"),
        ], any_order=True)


class ResourcesValidationTest(TestCase):
    def test_minimal_resources_config(self):
        """Charm has the minimum allowed resources configuration."""
        linter = Mock()
        charm = {
            'resources': {
                'test': {
                    'type': 'file',
                    'filename': 'file.tgz',
                }
            }
        }
        validate_resources(charm, linter)
        self.assertFalse(linter.err.called)

    def test_resources_without_defs(self):
        """Charm has resources key but no definitions."""
        linter = Mock()
        charm = {
            'resources': {}
        }
        validate_resources(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('resources: must be a dictionary of resource definitions'),
        ], any_order=True)

    def test_resources_invalid_values(self):
        """Charm has resources with invalid values."""
        linter = Mock()
        charm = {
            'resources': {
                'buzz': {
                    'type': 'snap',
                },
            }
        }
        validate_resources(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('resources.buzz.type: "snap" is not one of file, oci-image'),
        ], any_order=True)

    def test_resources_unknown_keys(self):
        """Charm has resources with illegal keys."""
        linter = Mock()
        charm = {
            'resources': {
                'vm': {
                    'type': 'file',
                    'unknown': 'invalid key',
                },
            }
        }
        validate_resources(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('resources.vm: Unrecognized keys in mapping: '
                 '"{\'unknown\': \'invalid key\'}"'),
        ], any_order=True)

    def test_resources_proof_extensions(self):
        """Charm has resources with proof extensions."""
        linter = Mock()
        charm = {
            'resources': {
                'vm': {
                    'type': 'file',
                    'unknown': 'invalid key',
                },
            }
        }
        extensions = [
            {
                'name': 'unknown',
                'type': 'String',
            },
            {
                'name': 'unknown_default',
                'type': 'String',
                'missing': '',
            }
        ]
        validate_resources(charm, linter, extensions)
        self.assertEqual(linter.err.call_args_list, [])


class PayloadsValidationTest(TestCase):
    def test_minimal_payloads_config(self):
        """Charm has the minimum allowed payloads configuration."""
        linter = Mock()
        charm = {
            'payloads': {
                'test': {
                    'type': 'docker',
                }
            }
        }
        validate_payloads(charm, linter)
        self.assertFalse(linter.err.called)

    def test_complete_payloads_config(self):
        """Charm has payloads using all types."""
        linter = Mock()
        charm = {
            'payloads': {
                'vm': {
                    'type': 'kvm',
                },
                'app-container': {
                    'type': 'docker',
                },
            }
        }
        validate_payloads(charm, linter)
        self.assertFalse(linter.err.called)

    def test_payloads_without_defs(self):
        """Charm has payloads key but no definitions."""
        linter = Mock()
        charm = {
            'payloads': {}
        }
        validate_payloads(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('payloads: must be a dictionary of payload definitions'),
        ], any_order=True)

    def test_payloads_invalid_values(self):
        """Charm has payloads with invalid values."""
        linter = Mock()
        charm = {
            'payloads': {
                'buzz': {
                    'type': 'dockerdockerdocker',
                },
            }
        }
        validate_payloads(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('payloads.buzz.type: "dockerdockerdocker" is not one of '
                 'kvm, docker'),
        ], any_order=True)

    def test_payloads_unknown_keys(self):
        """Charm has payloads with illegal keys."""
        linter = Mock()
        charm = {
            'payloads': {
                'vm': {
                    'type': 'kvm',
                    'unknown': 'invalid key',
                },
            }
        }
        validate_payloads(charm, linter)
        self.assertEqual(linter.err.call_count, 1)
        linter.err.assert_has_calls([
            call('payloads.vm: Unrecognized keys in mapping: '
                 '"{\'unknown\': \'invalid key\'}"'),
        ], any_order=True)

    def test_payloads_proof_extensions(self):
        """Charm has payloads with proof extensions."""
        linter = Mock()
        charm = {
            'payloads': {
                'vm': {
                    'type': 'kvm',
                    'unknown': 'invalid key',
                },
            }
        }
        extensions = [
            {
                'name': 'unknown',
                'type': 'String',
            }
        ]
        validate_payloads(charm, linter, extensions)
        self.assertEqual(linter.err.call_args_list, [])


class ActionsValidationTest(TestCase):
    def test_minimal_actions_config(self):
        """Charm has the minimum allowed actions configuration."""
        linter = Mock()
        actions = {
            'an-action': {}
        }
        validate_actions(actions, 'actions', linter)
        self.assertFalse(linter.err.called)

    def test_complete_actions_config(self):
        """Charm has multiple actions."""
        linter = Mock()
        actions = {
            'do': {
                'description': 'a thing',
            },
            'do-not': {
                'description': 'not a thing',
            },
        }
        with patch('os.path.exists'):
            validate_actions(actions, 'actions', linter)
        self.assertFalse(linter.err.called)

    def test_juju_actions_fail(self):
        """Charm has multiple actions."""
        linter = Mock()
        actions = {
            'juju-do': {
                'description': 'a thing',
            },
            'do-not': {
                'description': 'not a thing',
            },
        }

        with patch('os.path.exists'):
            validate_actions(actions, 'actions', linter)
        self.assertEqual(linter.err.call_count, 1)


class FunctionsValidationTest(TestCase):
    def test_minimal_actions_config(self):
        """Charm has the minimum allowed functions configuration."""
        linter = Mock()
        functions = {
            'an-function': {}
        }
        validate_functions(functions, 'functions', linter)
        self.assertFalse(linter.err.called)

    def test_complete_functions_config(self):
        """Charm has multiple functions."""
        linter = Mock()
        functions = {
            'do': {
                'description': 'a thing',
            },
            'do-not': {
                'description': 'not a thing',
            },
        }
        with patch('os.path.exists'):
            validate_functions(functions, 'functions', linter)
        self.assertFalse(linter.err.called)

    def test_juju_functions_fail(self):
        """Charm has multiple functions."""
        linter = Mock()
        functions = {
            'juju-do': {
                'description': 'a thing',
            },
            'do-not': {
                'description': 'not a thing',
            },
        }

        with patch('os.path.exists'):
            validate_functions(functions, 'functions', linter)
        self.assertEqual(linter.err.call_count, 1)


class SeriesValidationTest(TestCase):
    def test_series_not_list(self):
        """Charm has a series key, but the value is not a list."""
        linter = Mock()
        charm = {
            'series': 'trusty',
        }
        validate_series(charm, linter)
        linter.err.assert_called_once_with(
                'series: must be a list of series names')

    def test_series_list(self):
        """Charm has a series key that is a list."""
        linter = Mock()
        charm = {
            'series': ['trusty'],
        }
        validate_series(charm, linter)
        self.assertFalse(linter.err.called)

    def test_no_series(self):
        """Charm does not have a series key."""
        linter = Mock()
        charm = {}
        validate_series(charm, linter)
        self.assertTrue(linter.err.called)


class TermsValidationTest(TestCase):
    def test_terms_not_list(self):
        """Charm has a terms key, but the value is not a list."""
        linter = Mock()
        charm = {
            'terms': 'lorem-ipsum',
        }
        validate_terms(charm, linter)
        linter.err.assert_called_once_with(
                'terms: must be a list of term ids')

    def test_terms_list(self):
        """Charm has a terms key that is a list."""
        linter = Mock()
        charm = {
            'terms': ['lorem-ipsum'],
        }
        validate_terms(charm, linter)
        self.assertFalse(linter.err.called)

    def test_no_terms(self):
        """Charm does not have a terms key."""
        linter = Mock()
        charm = {}
        validate_terms(charm, linter)
        self.assertFalse(linter.err.called)


class MinJujuVersionValidationTest(TestCase):
    def test_invalid_version_formats(self):
        """Test invalid version formats"""
        linter = Mock()
        versions = [
            '2',  # need major.minor.patch
            '2.0',  # need major.minor.patch
            '2-beta3',  # missing minor
        ]
        for v in versions:
            charm = {
                'min-juju-version': v,
            }
            validate_min_juju_version(charm, linter)
            linter.err.assert_called_once_with(
                'min-juju-version: invalid format, try X.Y.Z')
            linter.reset_mock()

    def test_invalid_versions(self):
        """Test invalid versions (good format, bad version)"""
        linter = Mock()
        versions = [
            '1.25.3',  # need 2.0.0 or greater
        ]
        for v in versions:
            charm = {
                'min-juju-version': v,
            }
            validate_min_juju_version(charm, linter)
            linter.err.assert_called_once_with(
                'min-juju-version: invalid version, must be 2.0.0 or greater')
            linter.reset_mock()

    def test_valid_versions(self):
        """Test valid version formats"""
        linter = Mock()
        versions = [
            '2.0.1',
            '2.0.1.1',
            '2.1-beta2',
            '2.1-beta2.1',
        ]
        for v in versions:
            charm = {
                'min-juju-version': v,
            }
            validate_min_juju_version(charm, linter)
            self.assertFalse(linter.err.called)
            linter.reset_mock()


class ExtraBindingsValidationTest(TestCase):
    def test_invalid(self):
        """Charm has a invalid extra-bindings metadata."""
        linter = Mock()
        charm = {
            'extra-bindings': 'public',
        }
        validate_extra_bindings(charm, linter)
        linter.err.assert_called_once_with(
            'extra-bindings: must be a dictionary')

    def test_valid(self):
        """Charm has a valid extra-bindings metadata."""
        linter = Mock()
        charm = {
            'extra-bindings': {
                'public': None,
            }
        }
        validate_extra_bindings(charm, linter)
        self.assertFalse(linter.err.called)


if __name__ == '__main__':
    main()
