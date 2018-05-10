"""Unit test for juju_test"""

from __future__ import print_function

import os
import six
import unittest
import yaml

from contextlib import contextmanager
from charmtools import test as juju_test
from mock import patch, call, Mock, MagicMock


if six.PY3:
    _builtin__open = "builtins.open"
else:
    _builtin__open = "__builtin__.open"


RAW_ENVIRONMENTS_YAML = '''
default: gojuju
environments:
  gojuju:
    type: cloud
    access-key: xxx
    secret-key: yyy
    control-bucket: gojuju-xyxyz
    admin-secret: zyxyx
    default-series: world
  pyjuju:
    type: cloud
    access-key: xxx
    secret-key: yyy
    control-bucket: juju-xyxyz
    admin-secret: zyxyxy
    default-series: world
    juju-origin: ppa
    ssl-hostname-verification: true'''

PARSED_ENVIRONMENTS_YAML = yaml.safe_load(RAW_ENVIRONMENTS_YAML)


@contextmanager
def cd(directory):
    """A context manager to temporarily change current working dir, e.g.::

        >>> import os
        >>> os.chdir('/tmp')
        >>> with cd('/bin'): print(os.getcwd())
        /bin
        >>> print(os.getcwd())
        /tmp
    """
    cwd = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(cwd)


class Arguments(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        return None


class JujuTestPluginTest(unittest.TestCase):
    @patch('subprocess.check_output')
    def test_get_gojuju_version(self, mock_check_output):
        mock_check_output.side_effect = ['1.2.3-series-xxx']
        version = juju_test.get_juju_version()

        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)

        mock_check_output.assert_called_with(['juju', 'version'])

    @patch('subprocess.check_output')
    def test_get_pyjuju_version(self, mcheck_output):
        mcheck_output.side_effect = [Exception('Non-zero exit'), 'juju 8.6']
        version = juju_test.get_juju_version()

        self.assertEqual(version.major, 8)
        self.assertEqual(version.minor, 6)
        self.assertEqual(version.patch, 0)

        mcheck_output.assert_called_with(['juju', '--version'])

    @patch('subprocess.check_output')
    def test_get_juju_version_malformed(self, mcheck_output):
        mcheck_output.return_value = '1.2.3.45'
        version = juju_test.get_juju_version()

        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)

        mcheck_output.assert_called_once_with(['juju', 'version'])

    def test_convert_to_timedelta(self):
        self.assertEqual(300, juju_test.convert_to_timedelta('5m'))
        self.assertEqual(300, juju_test.convert_to_timedelta('300'))
        self.assertEqual(100, juju_test.convert_to_timedelta('100s'))
        self.assertEqual(100, juju_test.convert_to_timedelta(100))
        self.assertEqual(60, juju_test.convert_to_timedelta('1m'))
        self.assertEqual(60 * 60, juju_test.convert_to_timedelta('1h'))

    def test_conductor_find_tests(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests="dummy")
            c = juju_test.Conductor(args)
            results = c.find_tests()
            self.assertIn('00_setup', results)
            self.assertNotIn('helpers.bash', results)

    def test_conductor_find_tests_fails(self):
        with cd('tests_functional/charms/mod-spdy/'):
            args = Arguments(tests="dummy")
            self.assertRaises(juju_test.NoTests, juju_test.Conductor, args)

    def test_conductor_ignores_arbitrary_env(self):
        """Ensure that the conductor ignores other env vars."""
        os.environ['CHARMTOOLS_TEST'] = 'FOOBAR'
        args = Arguments(tests="dummy")
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            self.assertNotIn('CHARMTOOLS_TEST', c.env)

    def test_conductor_keeps_whitelist_env(self):
        """Ensure that the conductor copies the environment whitelist."""
        os.environ['PATH'] = 'FOOBAR'
        os.environ['SSH_AGENT_PID'] = 'FOOBAR'
        os.environ['SSH_AUTH_SOCK'] = 'FOOBAR'
        args = Arguments(tests="dummy")
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            self.assertEqual('FOOBAR', c.env['PATH'])
            self.assertEqual('FOOBAR', c.env['SSH_AGENT_PID'])
            self.assertEqual('FOOBAR', c.env['SSH_AUTH_SOCK'])

    def test_conductor_allows_addition_to_whitelist_env(self):
        """Ensure that the conductor copies the environment whitelist."""
        with cd('tests_functional/charms/test/'):
            os.environ['FOO'] = 'BAR'
            os.environ['BAR'] = 'BAZ'
            args = Arguments(tests="dummy")
            args.preserve_environment_variables = "FOO,BAR"
            c = juju_test.Conductor(args)
            self.assertEqual('BAR', c.env['FOO'])
            self.assertEqual('BAZ', c.env['BAR'])

    @patch.object(juju_test.Conductor, 'find_tests')
    def test_conductor_find_tests_exception(self, mfind_tests):
        mfind_tests.return_value = None
        args = Arguments(tests=None)
        self.assertRaises(juju_test.NoTests, juju_test.Conductor, args)

    @patch('subprocess.check_output')
    def test_conductor_status(self, mcheck_output):
        yml_output = '''
        machines:
            '0':
                agent-state: limbo
                agent-version: 999.999.999
                dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
                instance-id: j-xxxxxx
                series: world
        services: {}'''

        mcheck_output.side_effect = [yml_output, Exception('not bootstrapped')]
        juju_env = 'test'
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            results = c.status(juju_env)

            mcheck_output.assert_called_with(
                ['juju', 'status', '-e', juju_env], env=c.env)
            self.assertEqual(results, yaml.safe_load(yml_output))

            # Check to make sure we get None with juju status fails
            results = c.status('not-bootstrapped')
            self.assertEqual(results, None)

    @patch('os.path.exists')
    # @patch('__builtin__.open')
    @patch(_builtin__open )
    def test_conductor_load_envs_yaml(self, mock_open, mock_exists):
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = Mock()
        mock_open.return_value.read.return_value = RAW_ENVIRONMENTS_YAML
        mock_exists.return_value = True

        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            results = c.load_environments_yaml()
            mock_open.assert_called_once_with(
                os.path.join(
                    os.path.expanduser('~'),
                    '.juju', 'environments.yaml'), 'r')
            self.assertEqual(results, yaml.safe_load(RAW_ENVIRONMENTS_YAML))

    @patch('os.path.exists')
    def test_conductor_load_envs_yaml_error(self, mock_exists):
        mock_exists.return_value = False
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            self.assertRaises(IOError, c.load_environments_yaml)

    @patch.object(juju_test.Conductor, 'load_environments_yaml')
    def test_get_environment(self, mock_conductor_ley):
        mock_conductor_ley.return_value = yaml.safe_load(RAW_ENVIRONMENTS_YAML)

        juju_env = 'gojuju'
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            environment = c.get_environment(juju_env)

            self.assertEqual(
                environment,
                PARSED_ENVIRONMENTS_YAML['environments'][juju_env])

    @patch.object(juju_test.Conductor, 'load_environments_yaml')
    def test_get_environment_fails(self, mock_conductor_ley):
        mock_conductor_ley.side_effect = IOError

        juju_env = 'gojuju'
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)

            self.assertRaises(IOError, c.get_environment, juju_env)

    @patch.object(juju_test.Conductor, 'load_environments_yaml')
    def test_get_environment_notfound(self, mock_conductor_ley):
        mock_conductor_ley.return_value = yaml.safe_load(RAW_ENVIRONMENTS_YAML)

        juju_env = 'dont-exist'
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)

            self.assertRaises(KeyError, c.get_environment, juju_env)

    @patch('subprocess.check_call')
    def test_conductor_destroy(self, mock_check_call):
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=1, patch=1)
            good_env = 'valid'
            c.destroy(good_env)

            mock_check_call.assert_called_once_with(
                ['juju', 'destroy-environment',
                 '-y', '-e', good_env], env=c.env
            )

            mock_check_call.reset_mock()
            c.juju_version = juju_test.JujuVersion(major=1, minor=17, patch=0)
            c.destroy(good_env)

            mock_check_call.assert_called_once_with(
                ['juju', 'destroy-environment', '-y', good_env], env=c.env)

            mock_check_call.reset_mock()
            c.juju_version = juju_test.JujuVersion(major=0, minor=8, patch=0)
            c.destroy(good_env)

            expected_cmd = 'echo y | juju destroy-environment -e %s' % good_env
            mock_check_call.assert_called_once_with(
                expected_cmd, shell=True, env=c.env)

    @patch('subprocess.check_call')
    def test_conductor_destroy_failed(self, mock_check_call):
        from subprocess import CalledProcessError
        mock_check_call.side_effect = CalledProcessError('err', 'err', 'err')

        bad_env = 'invalid'

        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)
            self.assertRaises(juju_test.DestroyUnreliable, c.destroy, bad_env)

            mock_check_call.reset_mock()
            c.juju_version = juju_test.JujuVersion(major=0, minor=8, patch=0)
            self.assertRaises(juju_test.DestroyUnreliable, c.destroy, bad_env)

    @patch('time.sleep')
    @patch('subprocess.check_call')
    @patch.object(juju_test.Conductor, 'status')
    def test_conductor_bootstrap(self, mock_status, mcheck_output, msleep):
        goyml_output = '''
        machines:
            '0':
                agent-state: started
                agent-version: 999.999.999
                dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
                instance-id: j-xxxxxx
                series: world
        services: {}'''

        pyyml_output = '''
        machines:
            0:
                agent-state: running
                instance-state: exists
                dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
                instance-id: j-xxxxxx
                series: world
        services: {}'''

        gostatus_output = yaml.safe_load(goyml_output)
        pystatus_output = yaml.safe_load(pyyml_output)

        mock_status.side_effect = [None, gostatus_output, pystatus_output]
        juju_env = 'test-env'
        expected_cmd = ['juju', 'bootstrap', '-e', juju_env]

        args = Arguments(tests='dummy', upload_tools=False, constraints=False)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)

            c.bootstrap(juju_env)
            mcheck_output.assert_called_once_with(expected_cmd, env=c.env)

            # Cover python as well.
            mcheck_output.reset_mock()
            juju_env = 'test-env'
            expected_cmd = ['juju', 'bootstrap', '-e', juju_env]

            args = Arguments(
                tests='dummy', upload_tools=False,
                constraints=False)
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=0, minor=8, patch=0)

            c.bootstrap(juju_env)
            mcheck_output.assert_called_once_with(expected_cmd, env=c.env)

    @patch('time.sleep')
    @patch('subprocess.check_call')
    @patch.object(juju_test.Conductor, 'status')
    def test_conductor_bootstrap_go_opts(self, mstatus, mcheck_output, msleep):
        goyml_output = '''
        machines:
            '0':
                agent-state: started
                agent-version: 999.999.999
                dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
                instance-id: j-xxxxxx
                series: world
        services: {}'''

        gostatus_output = yaml.safe_load(goyml_output)
        mstatus.return_value = gostatus_output
        juju_env = 'test-env'
        expected_cmd = ['juju', 'bootstrap', '--upload-tools', '-e', juju_env]

        args = Arguments(tests='dummy', upload_tools=True, constraints=False)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)

            c.bootstrap(juju_env)
            mcheck_output.assert_called_once_with(expected_cmd, env=c.env)

            mcheck_output.reset_mock()
            const_cmd = [
                'juju', 'bootstrap', '--constraints', 'mem=8G,arch=arm',
                '-e', juju_env]

            args = Arguments(tests='dummy', upload_tools=False,
                             constraints='mem=8G,arch=arm')
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)

            c.bootstrap(juju_env)
            mcheck_output.assert_called_once_with(const_cmd, env=c.env)

    @patch('subprocess.check_call')
    def test_conductor_bootstrap_error(self, mcheck_output):
        from subprocess import CalledProcessError
        mcheck_output.side_effect = CalledProcessError('err', 'err', 'err')

        juju_env = 'bad-env'
        args = Arguments(tests='dummy', upload_tools=True, constraints=False)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)

            self.assertRaises(juju_test.BootstrapError, c.bootstrap, juju_env)

    @patch('subprocess.check_call')
    @patch.object(juju_test, 'timeout')
    @patch.object(juju_test.Conductor, 'status')
    def test_conductor_bootstrap_unreliable(self, mock_status, mtimeout,
                                            mcheck_output):
        goyml_output = '''
        machines:
            '0':
                agent-state: pending
                agent-version: 999.999.999
                dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
                instance-id: j-xxxxxx
                series: world
        services: {}'''

        gostatus_output = yaml.safe_load(goyml_output)
        mtimeout.side_effect = juju_test.TimeoutError
        mock_status.return_value = gostatus_output
        jenv = 'test-env'

        args = Arguments(tests='dummy', upload_tools=False, constraints=False)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=8, patch=0)

            self.assertRaises(
                juju_test.BootstrapUnreliable, c.bootstrap, jenv, 1)

    def test_conductor_isolate_environment(self):
        args = Arguments(tests='dummy')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            self.assertRaises(
                NotImplementedError, c.isolate_environment, 'dummy')

    def test_orchestra_map_status_code(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests='dummy')
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')

            self.assertEqual('pass', o.map_status_code(0))
            self.assertEqual('fail', o.map_status_code(1))
            self.assertEqual('skip', o.map_status_code(100))
            self.assertEqual('timeout', o.map_status_code(124))

    def test_orchestra_determine_status_pass(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests='dummy', on_timeout='pass')
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')

            self.assertEqual('fail', o.determine_status(1))
            self.assertEqual('skip', o.determine_status(100))
            self.assertEqual('pass', o.determine_status(0))
            self.assertEqual('pass', o.determine_status(124))

    def test_orchestra_determine_status_skip(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests='dummy', on_timeout='skip')
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')

            self.assertEqual('pass', o.determine_status(0))
            self.assertEqual('fail', o.determine_status(1))
            self.assertEqual('skip', o.determine_status(100))
            self.assertEqual('skip', o.determine_status(124))

    def test_orchestra_determine_status_fail(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(
                tests='dummy', on_timeout='fail',
                fail_on_skip=True)
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')

            self.assertEqual('pass', o.determine_status(0))
            self.assertEqual('fail', o.determine_status(1))
            self.assertEqual('fail', o.determine_status(100))
            self.assertEqual('fail', o.determine_status(124))

            # Cornercase, timeouts sent to skip
            # should ultimately fail do to args
            o.conductor.args.on_timeout = 'skip'
            self.assertEqual('fail', o.determine_status(124))

    def test_orchestra_print_status_pass(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests='dummy', on_timeout='pass')
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')
            o.log.status = MagicMock()

            o.print_status(0)
            o.log.status.assert_called_once_with('%s' % juju_test.TEST_PASS)

            o.log.status.reset_mock()
            o.print_status(124)
            o.log.status.assert_called_with(
                '%s (%s)' % (juju_test.TEST_PASS, juju_test.TEST_TIMEOUT))

    def test_orchestra_print_status_skip(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(tests='dummy', on_timeout='skip')
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')
            o.log.status = MagicMock()

            o.print_status(100)
            o.log.status.assert_called_once_with('%s' % juju_test.TEST_SKIP)

            o.log.status.reset_mock()
            o.print_status(124)
            o.log.status.assert_called_with(
                '%s (%s)' % (juju_test.TEST_SKIP, juju_test.TEST_TIMEOUT))

    def test_orchestra_print_status_fail(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(
                tests='dummy', on_timeout='fail',
                fail_on_skip=True)
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')
            o.log.status = MagicMock()

            o.print_status(1)
            o.log.status.assert_called_once_with('%s' % juju_test.TEST_FAIL)

            o.log.status.reset_mock()
            o.print_status(100)
            o.log.status.assert_called_with('%s (%s)' % (juju_test.TEST_FAIL,
                                                         juju_test.TEST_SKIP))

            o.log.status.reset_mock()
            o.print_status(124)
            o.log.status.assert_called_with(
                '%s (%s)' % (juju_test.TEST_FAIL, juju_test.TEST_TIMEOUT))

            o.conductor.args.on_timeout = 'skip'
            o.log.status.reset_mock()
            o.print_status(124)
            o.log.status.assert_called_with(
                '%s (%s)' % (juju_test.TEST_FAIL, juju_test.TEST_TIMEOUT))

    def test_orchestra_is_passing_code(self):
        with cd('tests_functional/charms/test/'):
            args = Arguments(
                tests='dummy', on_timeout='pass',
                fail_on_skip=False)
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')

            self.assertTrue(o.is_passing_code(0))
            self.assertTrue(o.is_passing_code(100))
            self.assertTrue(o.is_passing_code(124))
            self.assertFalse(o.is_passing_code(1))

            o.conductor.args.on_timeout = 'skip'
            self.assertTrue(o.is_passing_code(124))

            o.conductor.args.on_timeout = 'fail'
            self.assertFalse(o.is_passing_code(124))

            o.conductor.args.on_timeout = 'skip'
            o.conductor.args.fail_on_skip = True
            self.assertFalse(o.is_passing_code(100))
            self.assertFalse(o.is_passing_code(124))

    def test_orchestra_build_env(self):
        with cd('tests_functional/charms/test/'):
            juju_env = 'test'
            args = Arguments(tests='dummy', juju_env=juju_env)
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')
            expected_env = c.env
            expected_env['JUJU_ENV'] = juju_env

            o.build_env()
            self.assertEqual(expected_env, o.env)

    @patch('subprocess.check_call')
    def test_orchestra_rsync_py(self, mcheck_call):
        machine = 0
        juju_env = 'test'
        path = '/var/log/./juju/*'
        logdir = '/tmp/'
        args = Arguments(tests='dummy', juju_env=juju_env)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=0, minor=8, patch=2)
            o = juju_test.Orchestra(c, 'test/dummy')

            expected_cmd = ['rsync', '-a', '-v', '-z', '-R', '-e',
                            'juju ssh -e %s' % juju_env,
                            '%s:%s' % (machine, path), logdir]
            o.build_env()
            o.rsync(machine, path, logdir)

            mcheck_call.assert_called_once_with(expected_cmd, env=o.env)

    @patch('subprocess.check_call')
    @patch.object(juju_test.Conductor, 'status')
    def test_orchestra_rsync_go(self, mstatus, mcheck_call):
        goyml_output = '''
        machines:
          "0":
            agent-state: started
            agent-version: 1.10.0
            dns-name: juju-yy-yy-yy-yy.compute.cloudprovider.tld
            instance-id: j-yyyyyy
            series: precise
          "1":
            agent-state: started
            agent-version: 1.10.0
            dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
            instance-id: j-xxxxxx
            series: precise
        services:
          dummy:
            charm: cs:precise/dummy-999
            exposed: false
            units:
              dummy/0:
                agent-state: started
                agent-version: 1.10.0
                machine: "1"
                public-address: juju-xx-xx-xx-xx.compute.cloudprovider.tld'''

        goyml_parsed = yaml.safe_load(goyml_output)
        mstatus.return_value = goyml_parsed

        machine = '1'
        dns_name = goyml_parsed['machines']['1']['dns-name']
        juju_env = 'test'
        path = '/var/log/./juju/*'
        logdir = '/tmp/'
        args = Arguments(tests='dummy', juju_env=juju_env)
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=10, patch=0)
            o = juju_test.Orchestra(c, 'test/dummy')

            expected_cmd = ['rsync', '-a', '-v', '-z', '-R', '-e', 'ssh',
                            'ubuntu@%s:%s' % (dns_name, path), logdir]
            o.build_env()
            o.rsync(machine, path, logdir)

            mcheck_call.assert_called_once_with(expected_cmd, env=o.env)

    @patch.object(juju_test.Orchestra, 'rsync')
    @patch.object(juju_test.Conductor, 'status')
    def test_orchestra_archive_logs_go(self, mstatus, rsync):
        goyml_output = '''
        machines:
          "0":
            agent-state: started
            agent-version: 1.10.0
            dns-name: juju-yy-yy-yy-yy.compute.cloudprovider.tld
            instance-id: j-yyyyyy
            series: precise
          "1":
            agent-state: started
            agent-version: 1.10.0
            dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
            instance-id: j-xxxxxx
            series: precise
        services:
          dummy:
            charm: cs:precise/dummy-999
            exposed: false
            units:
              dummy/0:
                agent-state: started
                agent-version: 1.10.0
                machine: "1"
                public-address: juju-xx-xx-xx-xx.compute.cloudprovider.tld'''
        goyml_parsed = yaml.safe_load(goyml_output)
        mstatus.return_value = goyml_parsed

        juju_env = 'testing'
        args = Arguments(tests='dummy', juju_env=juju_env, logdir='/tmp')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=10, patch=0)
            o = juju_test.Orchestra(c, 'test/dummy')

            o.build_env()
            o.archive_logs()
            rsync.assert_has_calls([
                call(
                    0, '/var/./log/juju/*',
                    os.path.join(args.logdir, 'bootstrap', '')),
                call(
                    '1', '/var/./log/juju/*',
                    os.path.join(args.logdir, 'dummy', ''))
            ])

    @patch.object(juju_test.Orchestra, 'rsync')
    @patch.object(juju_test.Conductor, 'status')
    def test_orchestra_archive_logs_py(self, mstatus, rsync):
        pyyml_output = '''
        machines:
          0:
            agent-state: running
            dns-name: juju-yy-yy-yy-yy.compute.cloudprovider.tld
            instance-id: i-yyyyyy
            instance-state: running
          1:
            agent-state: running
            dns-name: juju-xx-xx-xx-xx.compute.cloudprovider.tld
            instance-id: i-xxxxxx
            instance-state: running
        services:
          dummy:
            charm: cs:precise/dummy-19
            relations: {}
            units:
              dummy/0:
                agent-state: started
                machine: 1
                public-address: juju-xx-xx-xx-xx.compute.cloudprovider.tld'''
        pyyml_parsed = yaml.safe_load(pyyml_output)
        mstatus.return_value = pyyml_parsed

        juju_env = 'testing'
        args = Arguments(tests='dummy', juju_env=juju_env, logdir='/tmp')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=0, minor=7, patch=0)
            o = juju_test.Orchestra(c, 'test/dummy')

            o.build_env()
            o.archive_logs()
            rsync.assert_has_calls([
                call(
                    0, '/var/./log/juju/*',
                    os.path.join(args.logdir, 'bootstrap', '')),
                call(
                    1, '/var/./log/juju/*',
                    os.path.join(args.logdir, 'dummy', '')),
                call(
                    1, '/var/lib/juju/units/./*/charm.log',
                    os.path.join(args.logdir, 'dummy', ''))
            ])

    @patch.object(juju_test.Conductor, 'status')
    def test_orchestra_archive_logs_status_fails(self, mstatus):
        mstatus.return_value = None

        args = Arguments(tests='dummy', juju_env='testing', logdir='/tmp')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            o = juju_test.Orchestra(c, 'test/dummy')
            o.build_env()

            self.assertRaises(juju_test.OrchestraError, o.archive_logs)

    @patch.object(juju_test.Orchestra, 'rsync')
    @patch.object(juju_test.Conductor, 'status')
    def test_orchestra_archive_logs_rsync_fails(self, mstatus, rsync):
        from subprocess import CalledProcessError
        mstatus.return_value = {'services': {'dummy': {'units': {'dummy/0':
                                {'machine': '1'}}}}, 'machines': {}}

        args = Arguments(tests='dummy', juju_env='testing', logdir='/tmp')
        with cd('tests_functional/charms/test/'):
            c = juju_test.Conductor(args)
            c.juju_version = juju_test.JujuVersion(major=1, minor=7, patch=0)
            o = juju_test.Orchestra(c, 'test/dummy')
            o.log.warn = MagicMock()
            o.build_env()

            rsync.side_effect = CalledProcessError('err', 'err', 'err')
            o.archive_logs()
            expected_warns = [call('Failed to fetch logs for bootstrap node'),
                              call('Failed to grab logs for dummy/0')]
            o.log.warn.assert_has_calls(expected_warns)


class TestCfgTest(unittest.TestCase):
    test_config = '''\
    options:
      timeout: 500
    substrates:
      order: include, skip
      include: local
      skip: "*"
    '''

    def test_init_str(self):
        t = juju_test.TestCfg(self.test_config)
        self.assertEqual(t.timeout, 500)
        self.assertEqual(t.substrates['include'], 'local')

    def test_init_dict(self):
        t = juju_test.TestCfg(yaml.safe_load(self.test_config))
        self.assertEqual(t.timeout, 500)
        self.assertEqual(t.substrates['include'], 'local')

    def test_update(self):
        t = juju_test.TestCfg(self.test_config)
        t.update(timeout=400)
        self.assertEqual(t.timeout, 400)
