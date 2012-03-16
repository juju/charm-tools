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

    def _make_juju_status_dict(self, num_units=1,
                               service_name='test-service'):
        """Generate valid juju status dict and return it."""
        machine_data = {}
        # The 0th machine is the Zookeeper.
        machine_data[0] = {
            'dns-name': 'zookeeper.example.com',
            'instance-id': 'machine0',
            'state': 'not-started',
            }
        service_data = {
            'charm': 'local:precise/{}-1'.format(service_name),
            'relations': {},
            'units': {},
            }
        for i in range(num_units):
            # The machine is always going to be i+1 because there
            # will always be num_units+1 machines.
            machine_number = i+1
            unit_machine_data = {
                'dns-name': 'machine{}.example.com'.format(machine_number),
                'instance-id': 'machine{}'.format(machine_number),
                'state': 'pending',
                'instance-state': 'pending',
                }
            machine_data[machine_number] = unit_machine_data
            unit_data = {
                'machine': machine_number,
                'public-address':
                    '{}-{}.example.com'.format(service_name, i),
                'relations': {},
                'state': 'pending',
                }
            service_data['units']['{}/{}'.format(service_name, i)] = (
                unit_data)
        juju_status_data = {
            'machines': machine_data,
            'services': {service_name: service_data},
            }
        return juju_status_data

    def _make_juju_status_yaml(self, num_units=1,
                               service_name='test-service'):
        """Convert the dict returned by `_make_juju_status_dict` to YAML."""
        return yaml.dump(self._make_juju_status_dict(num_units, service_name))

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

    def test_unit_info_returns_first_unit_by_default(self):
        # By default, unit_info() just returns the value of the
        # requested item for the first unit in a service.
        juju_yaml = self._make_juju_status_yaml(num_units=2)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        unit_address = charmhelpers.unit_info(
            'test-service', 'public-address')
        self.assertEqual('test-service-0.example.com', unit_address)

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

    def test_get_machine_data(self):
        # get_machine_data() returns a dict containing the machine data
        # parsed from juju status.
        juju_yaml = self._make_juju_status_yaml()
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        machine_0_data = charmhelpers.get_machine_data()[0]
        self.assertEqual('zookeeper.example.com', machine_0_data['dns-name'])

    def test_wait_for_machine_returns_if_machine_up(self):
        # If wait_for_machine() is called and the machine(s) it is
        # waiting for are already up, it will return.
        juju_status_dict = self._make_juju_status_dict()
        # We'll update machine #1 so that it's 'running'.
        juju_status_dict['machines'][1]['instance-state'] = 'running'
        juju_yaml = yaml.dump(juju_status_dict)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        machines, time_taken = charmhelpers.wait_for_machine(timeout=1)
        self.assertEqual(1, machines)

    def test_wait_for_machine_times_out(self):
        # If the machine that wait_for_machine is waiting for isn't
        # 'running' before the passed timeout is reached,
        # wait_for_machine will raise an error.
        juju_yaml = self._make_juju_status_yaml()
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertRaises(
            RuntimeError, charmhelpers.wait_for_machine, timeout=0)

    def test_wait_for_machine_always_returns_if_running_locally(self):
        # If juju is actually running against a local LXC container,
        # wait_for_machine will always return.
        juju_status_dict = self._make_juju_status_dict()
        # We'll update the 0th machine to make it look like it's an LXC
        # container.
        juju_status_dict['machines'][0]['dns-name'] = 'localhost'
        juju_yaml = yaml.dump(juju_status_dict)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        machines, time_taken = charmhelpers.wait_for_machine(timeout=1)
        # wait_for_machine will always return 1 machine started here,
        # since there's only one machine to start.
        self.assertEqual(1, machines)
        # time_taken will be 0, since no actual waiting happened.
        self.assertEqual(0, time_taken)

    def test_wait_for_machine_waits_for_multiple_machines(self):
        # Wait for machine can be told to wait for multiple machines.
        juju_status_dict = self._make_juju_status_dict(num_units=2)
        juju_status_dict['machines'][1]['instance-state'] = 'running'
        juju_status_dict['machines'][2]['instance-state'] = 'running'
        juju_yaml = yaml.dump(juju_status_dict)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        machines, time_taken = charmhelpers.wait_for_machine(num_machines=2)
        self.assertEqual(2, machines)

if __name__ == '__main__':
    unittest.main()
