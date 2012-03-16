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

    def _make_juju_status_yaml(self, num_units=1,
                               service_name='test-service'):
        """Generate valid juju status YAML and return it."""
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
        service_data = {
            'charm': 'local:precise/{}-1'.format(service_name),
            'relations': {},
            'units': {},
            }
        for i in range(num_units):
            unit_data = {
                'machine': i,
                'public-address':
                    '{}-{}.example.com'.format(service_name, i),
                'relations': {},
                'state': 'pending',
                }
            service_data['units']['{}/{}'.format(service_name, i)] = (
                unit_data)
        juju_status_data = {'services': {service_name: service_data}}
        return yaml.dump(juju_status_data)

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
        juju_yaml = self._make_juju_status_yaml()
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertEqual(
            'pending',
            charmhelpers.unit_info('test-service', 'state'))

    def test_unit_info_returns_empty_for_nonexistant_service(self):
        # If the service passed to unit_info() has not yet started (or
        # otherwise doesn't exist), unit_info() will return an empty
        # string.
        juju_yaml = "services: {}"
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertEqual(
            '', charmhelpers.unit_info('test-service', 'state'))

    def test_unit_info_accepts_data(self):
        # It's possible to pass a `data` dict, containing the parsed
        # result of juju status, to unit_info().
        juju_status_data = yaml.safe_load(
            self._make_juju_status_yaml())
        self.patch(charmhelpers, 'juju_status', lambda: None)
        service_data = juju_status_data['services']['test-service']
        unit_info_dict = service_data['units']['test-service/0']
        for key, value in unit_info_dict.items():
            item_info = charmhelpers.unit_info(
                'test-service', key, data=juju_status_data)
            self.assertEqual(value, item_info)

    def test_unit_info_accepts_unit_name(self):
        # By default, unit_info() just returns the value of the
        # requested item for the first unit in a service. However, it's
        # possible to pass a unit name to it, too.
        juju_yaml = self._make_juju_status_yaml(num_units=2)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        unit_address = charmhelpers.unit_info(
            'test-service', 'public-address', unit='test-service/1')
        self.assertEqual('test-service-1.example.com', unit_address)


if __name__ == '__main__':
    unittest.main()
