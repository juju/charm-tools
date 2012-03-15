# Tests for Python charm helpers.

import charmhelpers
import unittest
import yaml

from simplejson import dumps
from testtools import TestCase
from textwrap import dedent


class CharmHelpersTestCase(TestCase):
    """A basic test case for Python charm helpers."""

    def _patch_command(self, replacement_command):
        """Monkeypatch charmhelpers.command for testing purposes.

        :param replacement_command: The replacement Callable for
                                    command().
        """
        new_command = lambda *args: replacement_command
        self.patch(charmhelpers, 'command', new_command)

    def test_get_config(self):
        # get_config returns the contents of the current charm
        # configuration, as returned by config-get --format=json.
        mock_config = {'key': 'value'}

        # Monkey-patch shelltoolbox.command to avoid having to call out
        # to config-get. 
        self._patch_command(lambda: dumps(mock_config))
        self.assertEqual(mock_config, charmhelpers.get_config())

    def test_relation_get(self):
        # relation_get returns the value of a given relation variable,
        # as returned by relation-get $VAR.
        mock_relation_values = {
            'foo': 'bar',
            'spam': 'eggs',
            }
        self._patch_command(lambda *args: mock_relation_values[args[0]])
        self.assertEqual('bar', charmhelpers.relation_get('foo'))
        self.assertEqual('eggs', charmhelpers.relation_get('spam'))

    def test_relation_set(self):
        # relation_set calls out to relation-set and passes key=value
        # pairs to it.
        items_set = {}
        def mock_relation_set(*args):
            for arg in args:
                key, value = arg.split("=")
                items_set[key] = value
        self._patch_command(mock_relation_set)
        charmhelpers.relation_set(foo='bar', spam='eggs')
        self.assertEqual('bar', items_set.get('foo'))
        self.assertEqual('eggs', items_set.get('spam'))

    def test_make_charm_config_file(self):
        # make_charm_config_file() writes the passed configuration to a
        # temporary file as YAML.
        charm_config = {
            'foo': 'bar',
            'spam': 'eggs',
            'ham': 'jam',
            }
        # make_charm_config_file() returns the file object so that it
        # can be garbage collected properly.
        charm_config_file = charmhelpers.make_charm_config_file(charm_config)
        with open(charm_config_file.name) as config_in:
            written_config = config_in.read()
        self.assertEqual(yaml.dump(charm_config), written_config)

    def test_unit_info(self):
        # unit_info returns requested data about a given service.
        juju_yaml = dedent("""
            services:
              test-service:
                charm: local:oneiric/test-service-1
                relations: {}
                units:
                  test-service/0:
                    machine: 1
                    public-address: null
                    relations: {}
                    state: pending
            """)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertEqual(
            'pending',
            charmhelpers.unit_info('test-service', 'state'))

    def test_unit_info_returns_empty_for_nonexistant_service(self):
        # If the service passed to unit_info() has not yet started (or
        # otherwise doesn't exist), unit_info() will return an empty string.
        juju_yaml = "services: {}"
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertEqual(
            '', charmhelpers.unit_info('test-service', 'state'))


if __name__ == '__main__':
    unittest.main()
