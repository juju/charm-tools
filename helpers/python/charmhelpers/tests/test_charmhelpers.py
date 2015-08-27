# Tests for Python charm helpers.

import unittest
import yaml

from json import dumps
from StringIO import StringIO
from testtools import TestCase

import sys
# Path hack to ensure we test the local code, not a version installed in
# /usr/local/lib.  This is necessary since /usr/local/lib is prepended before
# what is specified in PYTHONPATH.
sys.path.insert(0, 'helpers/python')
import charmhelpers

from subprocess import CalledProcessError


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
                               service_name='test-service',
                               unit_state='pending',
                               machine_state='not-started'):
        """Generate valid juju status dict and return it."""
        machine_data = {}
        # The 0th machine is the Zookeeper.
        machine_data[0] = {'dns-name': 'zookeeper.example.com',
                           'instance-id': 'machine0',
                           'state': 'not-started'}
        service_data = {'charm': 'local:precise/{}-1'.format(service_name),
                        'relations': {},
                        'units': {}}
        for i in range(num_units):
            # The machine is always going to be i+1 because there
            # will always be num_units+1 machines.
            machine_number = i + 1
            unit_machine_data = {
                'dns-name': 'machine{}.example.com'.format(machine_number),
                'instance-id': 'machine{}'.format(machine_number),
                'state': machine_state,
                'instance-state': machine_state}
            machine_data[machine_number] = unit_machine_data
            unit_data = {
                'machine': machine_number,
                'public-address':
                '{}-{}.example.com'.format(service_name, i),
                'relations': {'db': {'state': 'up'}},
                'agent-state': unit_state}
            service_data['units']['{}/{}'.format(service_name, i)] = (
                unit_data)
        juju_status_data = {'machines': machine_data,
                            'services': {service_name: service_data}}
        return juju_status_data

    def _make_juju_status_yaml(self, num_units=1,
                               service_name='test-service',
                               unit_state='pending',
                               machine_state='not-started'):
        """Convert the dict returned by `_make_juju_status_dict` to YAML."""
        return yaml.dump(
            self._make_juju_status_dict(
                num_units, service_name, unit_state, machine_state))

    def test_get_config(self):
        # get_config returns the contents of the current charm
        # configuration, as returned by config-get --format=json.
        mock_config = {'key': 'value'}

        # Monkey-patch shelltoolbox.command to avoid having to call out
        # to config-get.
        self._patch_command(lambda: dumps(mock_config))
        self.assertEqual(mock_config, charmhelpers.get_config())

    def test_config_get(self):
        # config_get is used to retrieve individual configuration elements
        mock_config = {'key': 'value'}

        # Monkey-patch shelltoolbox.command to avoid having to call out
        # to config-get.
        self._patch_command(lambda *args: mock_config[args[0]])
        self.assertEqual(mock_config['key'], charmhelpers.config_get('key'))

    def test_unit_get(self):
        # unit_get is used to retrieve individual configuration elements
        mock_config = {'key': 'value'}

        # Monkey-patch shelltoolbox.command to avoid having to call out
        # to unit-get.
        self._patch_command(lambda *args: mock_config[args[0]])
        self.assertEqual(mock_config['key'], charmhelpers.unit_get('key'))

    def test_relation_get(self):
        # relation_get returns the value of a given relation variable,
        # as returned by relation-get $VAR.
        mock_relation_values = {
            'foo': 'bar',
            'spam': 'eggs'}
        self._patch_command(lambda *args: mock_relation_values[args[0]])
        self.assertEqual('bar', charmhelpers.relation_get('foo'))
        self.assertEqual('eggs', charmhelpers.relation_get('spam'))

        self._patch_command(lambda *args: mock_relation_values[args[2]])
        self.assertEqual('bar',
                         charmhelpers.relation_get('foo', 'test', 'test:1'))
        self.assertEqual('eggs',
                         charmhelpers.relation_get('spam', 'test', 'test:1'))

        self._patch_command(lambda *args: '%s' % mock_relation_values)
        self.assertEqual("{'foo': 'bar', 'spam': 'eggs'}",
                         charmhelpers.relation_get())

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

    def test_relation_ids(self):
        # relation_ids returns a list of relations id for the given
        # named relation
        mock_relation_ids = {'test': 'test:1 test:2'}
        self._patch_command(lambda *args: mock_relation_ids[args[0]])
        self.assertEqual(mock_relation_ids['test'].split(),
                         charmhelpers.relation_ids('test'))

    def test_relation_list(self):
        # relation_list returns a list of unit names either for the current
        # context or for the provided relation ID
        mock_unit_names = {'test:1': 'test/0 test/1 test/2',
                           'test:2': 'test/3 test/4 test/5'}

        # Patch command for current context use base - context = test:1
        self._patch_command(lambda: mock_unit_names['test:1'])
        self.assertEqual(mock_unit_names['test:1'].split(),
                         charmhelpers.relation_list())
        # Patch command for provided relation-id
        self._patch_command(lambda *args: mock_unit_names[args[1]])
        self.assertEqual(mock_unit_names['test:2'].split(),
                         charmhelpers.relation_list(rid='test:2'))

    def test_open_close_port(self):
        # expose calls open-port with port/protocol parameters
        ports_set = []

        def mock_open_port(*args):
            for arg in args:
                ports_set.append(arg)

        def mock_close_port(*args):
            if args[0] in ports_set:
                ports_set.remove(args[0])
        # Monkey patch in the open-port mock
        self._patch_command(mock_open_port)
        charmhelpers.open_port(80, "TCP")
        charmhelpers.open_port(90, "UDP")
        charmhelpers.open_port(100)
        self.assertTrue("80/TCP" in ports_set)
        self.assertTrue("90/UDP" in ports_set)
        self.assertTrue("100/TCP" in ports_set)
        # Monkey patch in the close-port mock function
        self._patch_command(mock_close_port)
        charmhelpers.close_port(80, "TCP")
        charmhelpers.close_port(90, "UDP")
        charmhelpers.close_port(100)
        # ports_set should now be empty
        self.assertEquals(len(ports_set), 0)

    def test_service_control(self):
        # Collect commands that have been run
        commands_set = {}

        def mock_service(*args):
            service = args[0]
            action = args[1]
            if service not in commands_set:
                commands_set[service] = []
            if ((len(commands_set[service]) > 1 and
                 commands_set[service][-1] == 'stop' and
                 action == 'restart')):
                # Service is stopped - so needs 'start'
                # action as restart will fail
                commands_set[service].append(action)
                raise CalledProcessError(1, repr(args))
            else:
                commands_set[service].append(action)

        result = ['start', 'stop', 'restart', 'start']

        # Monkey patch service command
        self._patch_command(mock_service)
        charmhelpers.service_control('myservice', 'start')
        charmhelpers.service_control('myservice', 'stop')
        charmhelpers.service_control('myservice', 'restart')
        self.assertEquals(result, commands_set['myservice'])

    def test_make_charm_config_file(self):
        # make_charm_config_file() writes the passed configuration to a
        # temporary file as YAML.
        charm_config = {'foo': 'bar',
                        'spam': 'eggs',
                        'ham': 'jam'}
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
            charmhelpers.unit_info('test-service', 'agent-state'))

    def test_unit_info_returns_empty_for_nonexistent_service(self):
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
        juju_yaml = self._make_juju_status_yaml(machine_state='running')
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
        # wait_for_machine can be told to wait for multiple machines.
        juju_yaml = self._make_juju_status_yaml(
            num_units=2, machine_state='running')
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        machines, time_taken = charmhelpers.wait_for_machine(num_machines=2)
        self.assertEqual(2, machines)

    def test_wait_for_unit_returns_if_unit_started(self):
        # wait_for_unit() will return if the service it's waiting for is
        # already up.
        juju_yaml = self._make_juju_status_yaml(
            unit_state='started', machine_state='running')
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        charmhelpers.wait_for_unit('test-service', timeout=0)

    def test_wait_for_unit_raises_error_on_error_state(self):
        # If the unit is in some kind of error state, wait_for_unit will
        # raise a RuntimeError.
        juju_yaml = self._make_juju_status_yaml(
            unit_state='start-error', machine_state='running')
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertRaises(RuntimeError, charmhelpers.wait_for_unit,
                          'test-service', timeout=0)

    def test_wait_for_unit_raises_error_on_timeout(self):
        # If the unit does not start before the timeout is reached,
        # wait_for_unit will raise a RuntimeError.
        juju_yaml = self._make_juju_status_yaml(
            unit_state='pending', machine_state='running')
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertRaises(RuntimeError, charmhelpers.wait_for_unit,
                          'test-service', timeout=0)

    def test_wait_for_relation_returns_if_relation_up(self):
        # wait_for_relation() waits for relations to come up. If a
        # relation is already 'up', wait_for_relation() will return
        # immediately.
        juju_yaml = self._make_juju_status_yaml(
            unit_state='started', machine_state='running')
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        charmhelpers.wait_for_relation('test-service', 'db', timeout=0)

    def test_wait_for_relation_times_out_if_relation_not_present(self):
        # If a relation does not exist at all before a timeout is
        # reached, wait_for_relation() will raise a RuntimeError.
        juju_dict = self._make_juju_status_dict(
            unit_state='started', machine_state='running')
        units = juju_dict['services']['test-service']['units']
        # We'll remove all the relations for test-service for this test.
        units['test-service/0']['relations'] = {}
        juju_dict['services']['test-service']['units'] = units
        juju_yaml = yaml.dump(juju_dict)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertRaises(
            RuntimeError, charmhelpers.wait_for_relation, 'test-service',
            'db', timeout=0)

    def test_wait_for_relation_times_out_if_relation_not_up(self):
        # If a relation does not transition to an 'up' state, before a
        # timeout is reached, wait_for_relation() will raise a
        # RuntimeError.
        juju_dict = self._make_juju_status_dict(
            unit_state='started', machine_state='running')
        units = juju_dict['services']['test-service']['units']
        units['test-service/0']['relations']['db']['state'] = 'down'
        juju_dict['services']['test-service']['units'] = units
        juju_yaml = yaml.dump(juju_dict)
        mock_juju_status = lambda: juju_yaml
        self.patch(charmhelpers, 'juju_status', mock_juju_status)
        self.assertRaises(
            RuntimeError, charmhelpers.wait_for_relation, 'test-service',
            'db', timeout=0)

    def test_wait_for_page_contents_returns_if_contents_available(self):
        # wait_for_page_contents() will wait until a given string is
        # contained within the results of a given url and will return
        # once it does.
        # We need to patch the charmhelpers instance of urllib2 so that
        # it doesn't try to connect out.
        test_content = "Hello, world."
        new_urlopen = lambda *args: StringIO(test_content)
        self.patch(charmhelpers.urllib2, 'urlopen', new_urlopen)
        charmhelpers.wait_for_page_contents(
            'http://example.com', test_content, timeout=0)

    def test_wait_for_page_contents_times_out(self):
        # If the desired contents do not appear within the page before
        # the specified timeout, wait_for_page_contents() will raise a
        # RuntimeError.
        # We need to patch the charmhelpers instance of urllib2 so that
        # it doesn't try to connect out.
        new_urlopen = lambda *args: StringIO("This won't work.")
        self.patch(charmhelpers.urllib2, 'urlopen', new_urlopen)
        self.assertRaises(
            RuntimeError, charmhelpers.wait_for_page_contents,
            'http://example.com', "This will error", timeout=0)

    def test_log(self):
        # The "log" function forwards a string on to the juju-log command.
        logged = []

        def juju_log(*args):
            logged.append(args)
        charmhelpers.log('This is a log message', juju_log)
        # Since we only logged one message, juju-log was only called once..
        self.assertEqual(len(logged), 1)
        # The message was included in the arguments passed to juju-log.
        self.assertIn('This is a log message', logged[0])

    def test_log_escapes_message(self):
        # The Go version of juju-log interprets any string begining with two
        # hyphens ("--") as a command-line switch, even if the third character
        # is non-alphanumeric.  This is different behavior than the Python
        # version of juju-log.  Therefore we signfiy the end of options by
        # inserting the string " -- " just before the log message.
        logged = []

        def juju_log(*args):
            logged.append(args)
        charmhelpers.log('This is a log message', juju_log)
        # The call to juju-log includes the " -- " string before the message.
        self.assertEqual([('--', 'This is a log message')], logged)

    def test_log_entry(self):
        # The log_entry function logs a message about the script starting.
        logged = []
        self.patch(charmhelpers, 'log', logged.append)
        self.patch(charmhelpers, 'script_name', lambda: 'SCRIPT-NAME')
        charmhelpers.log_entry()
        self.assertEqual(['--> Entering SCRIPT-NAME'], logged)

    def test_log_exit(self):
        # The log_exit function logs a message about the script ending.
        logged = []
        self.patch(charmhelpers, 'log', logged.append)
        self.patch(charmhelpers, 'script_name', lambda: 'SCRIPT-NAME')
        charmhelpers.log_exit()
        self.assertEqual(['<-- Exiting SCRIPT-NAME'], logged)


if __name__ == '__main__':
    unittest.main()
