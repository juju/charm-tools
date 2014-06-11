#!/usr/bin/python
# coding=utf-8

import argparse
import glob
import logging
import os
import re
import signal
import subprocess
import sys
import time
import yaml
from datetime import timedelta
from collections import OrderedDict
from contextlib import contextmanager

TEST_PASS = '✔'
TEST_FAIL = '✘'
TEST_SKIP = '↷'
TEST_TIMEOUT = '⌛'
TEST_STATUS = {'pass': TEST_PASS, 'fail': TEST_FAIL, 'skip': TEST_SKIP,
               'timeout': TEST_TIMEOUT}
TEST_RESERVED_EXITS = {0: 'pass', 100: 'skip', 124: 'timeout'}

LOG_LEVELS = [logging.INFO, logging.DEBUG]
TEST_RESULT_LEVELV_NUM = 51
ENV_WHITELIST = ['PATH', 'SSH_AUTH_SOCK', 'SSH_AGENT_PID', 'PYTHONPATH']


class NoTests(Exception):
    pass


class BootstrapError(Exception):
    pass


class BootstrapUnreliable(Exception):
    pass


class DestroyUnreliable(Exception):
    pass


class SubstrateMismatch(Exception):
    pass


class TimeoutError(Exception):
    def __init__(self, value="Timed Out"):
        self.value = value


class TestingError(Exception):
    pass


class OrchestraError(Exception):
    pass


class Conductor(object):
    def __init__(self, arguments=None):
        self.args = arguments
        # Default home to what juju defaults to, can be overridden with "-p"
        self.env = {'JUJU_HOME': os.path.expanduser('~/.juju')}
        if arguments.preserve_environment_variables:
            for var in arguments.preserve_environment_variables.split(","):
                ENV_WHITELIST.append(var)
        for var in ENV_WHITELIST:
            if var in os.environ:
                self.env[var] = os.environ[var]
        self.log = logging.getLogger('juju-test.conductor')
        self.tests = self.find_tests()
        self.tests_requested = self.args.tests
        self.juju_version = None
        self.juju_env = self.args.juju_env
        self.errors = 0
        self.fails = 0
        self.passes = 0

        if self.tests_requested:
            self.tests_requested = [os.path.basename(t) for t in
                                    self.tests_requested]

        if not self.tests:
            raise NoTests()

    def run(self):
        self.juju_version = get_juju_version()
        requested_tests = self.tests
        if self.tests_requested:
            for test in self.tests:
                if test not in self.tests_requested:
                    del self.tests[test]

        for test in requested_tests.values():
            try:
                self.bootstrap(self.juju_env, self.args.setup_timeout)
            except Exception, e:
                self.log.warn('Could not bootstrap %s, got %s. Skipping' %
                              (self.juju_env, e))
                self.errors += 1
                continue

            try:
                t = Orchestra(self, test)
                t.perform()
            except:
                self.fails += 1
                if self.args.set_e:
                    self.log.info('Breaking here as requested by --set-e')
                    return self.errors, self.fails, self.passes
            else:
                self.passes += 1

            try:
                self.destroy(self.juju_env)
            except DestroyUnreliable:
                self.log.warn('Unable to destroy bootstrap, trying again')
                time.sleep(2)
                try:
                    self.destroy(self.juju_env)
                except:
                    continue

        return self.errors, self.fails, self.passes

    def find_tests(self):
        tests_dir = glob.glob(os.path.join('tests', '*'))
        if not tests_dir:
            return None

        # Filter out only the files in tests/ then get the test names.
        tests = [t for t in tests_dir if os.path.isfile(t)]
        # only include executables
        tests = [(os.path.basename(t), t) for t in tests if
                 os.access(t, os.R_OK | os.X_OK)]

        result = OrderedDict()
        # keep sort order as well as indexed lookups
        for basename, test in sorted(tests):
            result[basename] = test
        return result

    def safe_test_name(self, test_name):
        return test_name

    def isolate_environment(self, juju_env):
        # Should probably do something other than NotImplementedError...
        raise NotImplementedError()

    def get_environment(self, juju_env):
        juju_home = self.env['JUJU_HOME']
        try:
            env_yaml = self.load_environments_yaml(juju_home)
        except IOError:
            raise  # Do something more clever here?

        if not juju_env in env_yaml['environments']:
            raise KeyError('%s does not exist in %s/environments.yaml' %
                           (juju_env, juju_home))

        return env_yaml['environments'][juju_env]

    def bootstrap(self, juju_env, wait_for=400):
        self.log.debug('Starting a bootstrap for %s, kill after %s'
                       % (juju_env, wait_for))
        cmd = ['juju', 'bootstrap']
        if self.juju_version.major > 0:
            if self.args.upload_tools:
                cmd.append('--upload-tools')
        if self.args.constraints:
            cmd.extend(['--constraints', self.args.constraints])
        cmd.extend(['-e', juju_env])

        self.log.debug('Running the following: %s' % ' '.join(cmd))
        try:
            subprocess.check_call(cmd, env=self.env)
        except subprocess.CalledProcessError:
            raise BootstrapError('Bootstrap returned with an exit > 0')

        self.log.debug('Waiting for bootstrap')
        try:
            with timeout(wait_for):
                self.wait_for_bootstrap(juju_env)
        except TimeoutError:
            try:
                self.destroy(self.juju_env)
            except:
                pass

            raise BootstrapUnreliable('Bootstrap timeout after %ss' % wait_for)

    def destroy(self, juju_env):
        self.log.debug('Tearing down %s juju environment' % juju_env)
        cmd = ['juju', 'destroy-environment']

        if self.juju_version.major > 0:
            if self.juju_version.minor < 17:
                cmd.extend(['-y', '-e', juju_env])
            else:
                cmd.extend(['-y', juju_env])

            self.log.debug('Calling "%s"' % ' '.join(cmd))
            try:
                subprocess.check_call(cmd, env=self.env)
            except subprocess.CalledProcessError:
                raise DestroyUnreliable('Unable to destroy %s' % juju_env)
        else:
            # Probably should use Popen instead of Shell=True. I'm just not
            # confident on properly mocking a Popen call just yet.
            cmd.extend(['-e', juju_env])
            pycmd = 'echo y | %s' % ' '.join(cmd)
            self.log.debug('Calling "%s"' % pycmd)
            try:
                subprocess.check_call(pycmd, shell=True, env=self.env)
            except subprocess.CalledProcessError:
                raise DestroyUnreliable('Unable to destroy %s' % juju_env)

    def status(self, juju_env):
        cmd = ['juju', 'status', '-e', juju_env]
        self.log.debug('Running the following: %s' % ' '.join(cmd))
        try:
            output = subprocess.check_output(cmd, env=self.env)
        except:
            self.log.debug('Status command failed, returning nothing')
            return None

        return yaml.safe_load(output)

    def wait_for_bootstrap(self, juju_env):
        bootstrapped = False
        while not bootstrapped:
            self.log.debug('Still not bootstrapped')
            time.sleep(5)
            status = self.status(juju_env)
            if not status:
                continue

            if self.juju_version.major > 0:
                self.log.debug('State for %s: %s' %
                               (self.juju_version,
                                status['machines']['0']['agent-state']))
                if status['machines']['0']['agent-state'] == 'started':
                    bootstrapped = True
            else:
                self.log.debug('State for %s: %s' %
                               (self.juju_version,
                                status['machines'][0]['agent-state']))
                if status['machines'][0]['agent-state'] == 'running':
                    bootstrapped = True

    def load_environments_yaml(self, juju_home='~/.juju'):
        env_yaml_file = os.path.join(os.path.expanduser(juju_home),
                                     'environments.yaml')
        if not os.path.exists(env_yaml_file):
            raise IOError("%s file does not exist" % env_yaml_file)
        with open(env_yaml_file, 'r') as y:
            return yaml.safe_load(y.read())


class Orchestra(object):
    def __init__(self, conductor, arrangement):
        self.conductor = conductor
        self.test = arrangement
        self.name = os.path.basename(self.test)
        self.safe_name = self.conductor.safe_test_name(self.name)
        self.log = logging.getLogger('juju-test.conductor.%s' % self.safe_name)
        self.archive = self.conductor.args.logdir
        self.env = self.conductor.env

    def perform(self):
        self.build_env()
        error = None
        self.log.debug('Running %s (%s)' % (self.name, self.test))
        try:
            with timeout(self.conductor.args.timeout):
                output = subprocess.check_output(self.test, env=self.env)
                self.log.debug(output)
        except TimeoutError, e:
            self.log.debug('Killed by timeout after %s seconds',
                           self.conductor.args.timeout)
            self.print_status(124)
            error = e if not self.is_passing_code(124) else e
        except subprocess.CalledProcessError, e:
            self.log.debug(e.output)
            self.log.debug('Got exit code: %s', e.returncode)
            self.print_status(e.returncode)
            error = TestingError(e.returncode) if not \
                self.is_passing_code(e.returncode) else e
        except Exception, e:
            self.log.debug('Encountered unexpected error %s', e)
            self.print_status(9001)
            error = e
        else:
            self.print_status(0)

        if self.conductor.args.logdir:
            try:
                self.archive_logs()
            except OrchestraError, e:
                self.log.error(e)

        if error:
            raise error

    def archive_logs(self):
        logs = ['/var/./log/juju/*']
        status = self.conductor.status(self.env["JUJU_ENV"])
        logdir = self.conductor.args.logdir
        if not status:
            # Something is wrong, we need to throw up an archive error
            raise OrchestraError('Unable to query juju status')

        services = status['services']
        # machines = status['machines']

        if self.conductor.juju_version.major == 0:
            logs.append('/var/lib/juju/units/./*/charm.log')

        try:
            self.rsync(0, logs[0], os.path.join(logdir, 'bootstrap', ''))
        except:
            self.log.warn('Failed to fetch logs for bootstrap node')

        for service in services:
            for unit in services[service]['units']:
                machine = services[service]['units'][unit]['machine']
                for log in logs:
                    try:
                        self.rsync(machine, log, os.path.join(logdir, service,
                                                              ''))
                    except:
                        self.log.warn('Failed to grab logs for %s' % unit)

    def print_status(self, exit_code):
        actual = self.map_status_code(exit_code)
        computed = self.determine_status(exit_code)

        if actual != computed:
            self.log.status('%s (%s)' % (TEST_STATUS[computed],
                                         TEST_STATUS[actual]))
        else:
            self.log.status(TEST_STATUS[actual])

    # The next three methods need to be collapsed and consolidated
    def determine_status(self, exit_code):
        if exit_code == 124:
            timeout_status = self.conductor.args.on_timeout
            reversed_codes = {v: k for k, v in TEST_RESERVED_EXITS.items()}
            if timeout_status in reversed_codes.keys():
                exit_code = reversed_codes[self.conductor.args.on_timeout]
            else:
                return timeout_status

        if not exit_code in TEST_RESERVED_EXITS.keys():
            return 'fail'

        if exit_code == 100 and self.conductor.args.fail_on_skip:
            return 'fail'
        elif exit_code == 100:
            return 'skip'

        if exit_code == 0:
            return 'pass'

    def is_passing_code(self, exit_code):
        if exit_code == 124:
            timeout_status = self.conductor.args.on_timeout
            reversed_codes = {v: k for k, v in TEST_RESERVED_EXITS.items()}
            if timeout_status in reversed_codes.keys():
                exit_code = reversed_codes[self.conductor.args.on_timeout]

        if exit_code == 0:
            return True
        if exit_code == 100 and not self.conductor.args.fail_on_skip:
            return True

        return False

    def map_status_code(self, exit_code):
        if exit_code in TEST_RESERVED_EXITS.keys():
            return TEST_RESERVED_EXITS[exit_code]
        else:
            return 'fail'

    def build_env(self):
        self.env["JUJU_ENV"] = self.conductor.juju_env

    def rsync(self, machine, path, dest):
        if self.conductor.juju_version.major == 0:
            cmd = ['rsync', '-a', '-v', '-z', '-R', '-e', 'juju ssh -e %s' %
                   self.env['JUJU_ENV'], '%s:%s' % (machine, path), dest]
        else:  # http://pad.lv/1183159
            status = self.conductor.status(self.env['JUJU_ENV'])
            dns_name = status['machines'][machine]['dns-name']
            cmd = ['rsync', '-a', '-v', '-z', '-R', '-e', 'ssh',
                   'ubuntu@%s:%s' % (dns_name, path), dest]

        subprocess.check_call(cmd, env=self.env)


# Build Juju class instead? Move bootstrap, wait_for_bootstrap, teardown?
class JujuVersion(object):
    def __init__(self, major=0, minor=0, patch=0):
        self.mapping = ['major', 'minor', 'patch']
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self):
        return '.'.join(str(v) for v in [self.major, self.minor, self.patch])


class TestCfg(object):
    _keys = ['timeout', 'set-e', 'on-timeout', 'fail-on-skip', 'tests']

    def __init__(self, cfg):
        self.log = logging.getLogger('juju-test.testcfg')

        if isinstance(cfg, basestring):
            cfg = yaml.safe_load(cfg)

        if 'options' in cfg:
            for key, val in cfg['options'].iteritems():
                if key in self._keys:
                    setattr(self, key, val)
        if 'substrates' in cfg:
            self.substrates = cfg['substrates']

    def update(self, **kw):
        for key, val in kw.iteritems():
            self.log.debug('Overwriting %s to %s from cmd' % (key, val))
            setattr(self, key, val)


def get_juju_version():
    jv = JujuVersion()
    cmd = ['juju', 'version']
    try:
        version = subprocess.check_output(cmd)
        version = version.split('-')[0]
    except:
        cmd[1] = '--version'
        version = subprocess.check_output(cmd)
        version = version.split()[1]

    for i, ver in enumerate(version.split('.')):
        try:
            setattr(jv, jv.mapping[i], int(ver))
        except:
            break  # List out of range? Versions not semantic? Not my problem.

    return jv


def setup_logging(level=0, quiet=False, logdir=None):
    logger = logging.getLogger('juju-test')
    ft = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s: %(message)s')
    cmt = logging.Formatter('%(name)s %(levelname)-8s: %(message)s')
    logger.setLevel(1)

    if level >= len(LOG_LEVELS):
        level = len(LOG_LEVELS) - 1

    if logdir:
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        logfile = os.path.join(logdir, 'juju-test.%s.log' % int(time.time()))
        fh = logging.FileHandler(logfile)
        # Always at least log to INFO for file, unless DEBUG is requested
        fh.setLevel(LOG_LEVELS[level])
        fh.setFormatter(ft)
        logger.addHandler(fh)

    if not quiet:
        ch = logging.StreamHandler()
        ch.setLevel(LOG_LEVELS[level])
        ch.setFormatter(cmt)
        logger.addHandler(ch)

    return logger


class SubstrateFilter(object):
    def __init__(self, spec):
        self.order = spec.get('order', ['include', 'skip'])
        self.include = spec.get('include', ['*'])
        self.skip = spec.get('skip', [])

        if isinstance(self.order, str):
            self.order = [s.strip() for s in self.order.split(',')]
        if self.order != ['include', 'skip'] and \
                self.order != ['skip', 'include']:
            raise ValueError(
                'order should be defined using only include and skip')

        if isinstance(self.include, str):
            self.include = [self.include]
        self.include = set(self.include)

        if isinstance(self.skip, str):
            self.skip = [self.skip]
        self.skip = set(self.skip)

    def filter(self, substrates):
        """
        Filter a list of substrates relative to the rules generated on class
        creation.
        """
        if isinstance(substrates, str):
            substrates = [s.strip() for s in re.split('[,\s]', substrates)]

        # Apply the rules to the list of substrates returning anything that
        # matches
        if self.order == ['include', 'skip']:
            result = self._filter_includes(substrates, True)
            result = self._filter_skips(result)
        else:
            result = self._filter_skips(substrates, True)
            result = self._filter_includes(result)
        return result

    def _filter_includes(self, inputList, priority=False):
        if priority and '*' in self.include:
            return inputList
        return sorted(list(set(inputList).intersection(self.include)))

    def _filter_skips(self, inputList, priority=False):
        if priority and '*' in self.skip:
            return list(self.include.intersection(inputList))
        return sorted(list(set(inputList).difference(self.skip)))


def parse_substrates(spec):
    """Return a :class:`SubstrateFilter` object parsed from ``spec``.

    :param spec:

        Can be a yaml string, a dict with a 'substrates' key, or an object
        with a 'substrates' attribute. The 'substrates' key or attribute
        should contain a dict with optional 'order', 'skip', and 'include'
        keys.

    """
    if isinstance(spec, basestring):
        spec = yaml.safe_load(spec)
    elif not hasattr(spec, '__getitem__'):
        spec = vars(spec)
    if not spec or 'substrates' not in spec:
        raise ValueError(
            "Invalid data passed to parse_substrates: {}".format(spec))

    specRules = SubstrateFilter(spec['substrates'])
    return specRules


def allowed_substrates(spec, possible_substrates):
    return parse_substrates(spec).filter(possible_substrates)


def setup_parser():
    parser = argparse.ArgumentParser(
        prog='juju test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Execute a charms functional tests',
        epilog="""\
`%(prog)s` should always be run from within a CHARM_DIR.

examples:

  Given the following example charm layout:
    .
    ├── config.yaml
    ├── copyright
    ├── hooks
    │   └── ...
    ├── icon.svg
    ├── metadata.yaml
    ├── README.md
    └── tests
        ├── 00-tool_setup
        ├── 01-standard
        ├── 02-at_scale
        └── 03-different_database

  Run all tests for current charm
    %(prog)s

  Run one or more tests
    %(prog)s 01-standard 03-different_database

output:

  Each unit test will return an output in the form or either:

    RESULT   : SYM

  or

    RESULT   : SYM (SYM)

  Where SYM is a Symbol representing PASS: ✔, FAIL: ✘, SKIP: ↷, or TIMEOUT: ⌛
  In the event a status is rewritten by either the --fail-on-skip flag or the
  --on-timeout flag the original status will be displayed in () next to the
  computed status.
  """)
    # Plugin specific
    parser.add_argument('--description', action="store_true",
                        help="produces one-line description for juju-core")
    # Tester specific
    # Options ommited from jitsu: --archive-only, --no-bootstrap
    parser.add_argument('--timeout', default=600, action=StoreTimedelta,
                        help="timeout per unit test. Examples: 10m, 300s")
    parser.add_argument('--isolate', metavar='JUJU_ENV',
                        help="create unique environment cloned from JUJU_ENV")
    parser.add_argument('-o', '--logdir',
                        help="directory to store service logs from each test")
    # New tester options
    parser.add_argument('--setup-timeout', default=300, action=StoreTimedelta,
                        help="timeout to wait for an environment to be set up")
    parser.add_argument('--fail-on-skip', default=False, action="store_true",
                        help="treat SKIP (100) status as a failure, will \
                              halt execution with --set-e")
    parser.add_argument('--on-timeout', default='skip',
                        choices=['fail', 'skip', 'pass'],
                        help="treat tests which timeout as (fail, skip, pass)")
    parser.add_argument('--set-e', default=False, action="store_true",
                        help="stop testing execution on first failed test")
    parser.add_argument('-v', action='count', default=0,
                        help="make test more verbose")
    parser.add_argument('-q', '--quiet', default=False, action="store_true",
                        help="quiet all output")
    parser.add_argument('-p', '--preserve-environment-variables',
                        help="Comma separated list of environment variables "
                        "to preserve.  This will be added to the default list "
                        "of {}.".format(ENV_WHITELIST))
    # These are bootstrap/juju specific
    parser.add_argument('-e', '--environment', metavar='JUJU_ENV',
                        default=os.environ.get('JUJU_ENV'),
                        dest='juju_env',
                        #required=True,
                        help="juju environment to operate in")
    parser.add_argument('--upload-tools', default=False, action="store_true",
                        help="upload juju tools (available for juju > 1.x)")
    parser.add_argument('--constraints', help="juju environment constraints")
    # General options
    # TODO: Need to add some way to specify a particular test without
    #       colliding with CHARM
    parser.add_argument('tests', metavar="TEST", nargs='*',
                        default=None,
                        help="tests to execute, relative to tests/ directory, \
                              default is all")
    return parser


# http://stackoverflow.com/a/11784984/196832
def status(self, message, *args, **kws):
    self._log(TEST_RESULT_LEVELV_NUM, message, args, **kws)

logging.addLevelName(TEST_RESULT_LEVELV_NUM, "RESULT")
logging.Logger.status = status


def main():
    p = setup_parser()
    args = p.parse_args()
    test_cfg = None
    if args.description:
        print p.description
        sys.exit()

    logger = setup_logging(level=args.v, quiet=args.quiet, logdir=args.logdir)
    logger.info('Starting test run on %s using Juju %s'
                % (args.juju_env, get_juju_version()))
    logger.debug('Loading configuration options from testplan YAML')
    test_plans = glob.glob(os.path.join(os.getcwd(), 'tests',
                                        'test_config.y*ml'))
    if test_plans:
        with open(test_plans[0]) as f:
            test_cfg = f.read()

    if test_cfg:
        cfg = TestCfg(test_cfg)
        cfg.update(**vars(args))
    else:
        cfg = args

    logger.debug('Creating a new Conductor')
    try:
        tester = Conductor(args)
        env_yaml = tester.get_environment(cfg.juju_env)
        if getattr(cfg, 'substrates', None):
            rules = parse_substrates(cfg)
            allowed = rules.filter(env_yaml['type'])
            if env_yaml['type'] not in allowed:
                raise Exception('%s is not an allowed substrate: %s' %
                                (env_yaml['type'],
                                 allowed.join(', ')))
        errors, failures, passes = tester.run()
    except NoTests:
        logger.critical('No tests were found')
        sys.exit(1)
    except Exception as e:
        logger.critical(str(e))
        sys.exit(1)
    except:
        raise

    logger.info('Results: %s passed, %s failed, %s errored' %
                (passes, failures, errors))
    if failures > 0:
        sys.exit(failures)
    elif errors > 0:
        sys.exit(124)  # Nothing failed, but there were errors!

    sys.exit(0)


# http://stackoverflow.com/a/601168/196832
@contextmanager
def timeout(seconds):
    def signal_handler(signum, frame):
        raise TimeoutError()
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


class StoreTimedelta(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, convert_to_timedelta(values))


# http://bit.ly/13Mi5QV
def convert_to_timedelta(time_val):
    if isinstance(time_val, int):
        return time_val

    if time_val.isdigit():
        return int(time_val)

    num = int(time_val[:-1])
    if time_val.endswith('s'):
        return timedelta(seconds=num).seconds
    elif time_val.endswith('m'):
        return timedelta(minutes=num).seconds
    elif time_val.endswith('h'):
        return timedelta(hours=num).seconds


if __name__ == '__main__':
    main()
