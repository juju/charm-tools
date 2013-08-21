# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper functions for writing Juju charms in Python."""

__metaclass__ = type
__all__ = ['get_config',
           'log',
           'log_entry',
           'log_exit',
           'relation_get',
           'relation_set',
           'relation_ids',
           'relation_list',
           'config_get',
           'unit_get',
           'open_port',
           'close_port',
           'service_control',
           'unit_info',
           'wait_for_machine',
           'wait_for_page_contents',
           'wait_for_relation',
           'wait_for_unit',
           ]

from collections import namedtuple
import json
import operator
from shelltoolbox import (
    command,
    script_name,
    run,
)
import tempfile
import time
import urllib2
import yaml
from subprocess import CalledProcessError


SLEEP_AMOUNT = 0.1
Env = namedtuple('Env', 'uid gid home')
# We create a juju_status Command here because it makes testing much,
# much easier.
juju_status = lambda: command('juju')('status')


def log(message, juju_log=command('juju-log')):
    return juju_log('--', message)


def log_entry():
    log("--> Entering {}".format(script_name()))


def log_exit():
    log("<-- Exiting {}".format(script_name()))


def get_config():
    _config_get = command('config-get', '--format=json')
    return json.loads(_config_get())


def relation_get(attribute=None, unit=None, rid=None):
    cmd = command('relation-get')
    if attribute is None and unit is None and rid is None:
        return cmd().strip()
    _args = []
    if rid:
        _args.append('-r')
        _args.append(rid)
    if attribute is not None:
        _args.append(attribute)
    if unit:
        _args.append(unit)
    return cmd(*_args).strip()


def relation_set(**kwargs):
    cmd = command('relation-set')
    args = ['{}={}'.format(k, v) for k, v in kwargs.items()]
    cmd(*args)


def relation_ids(relation_name):
    cmd = command('relation-ids')
    args = [relation_name]
    return cmd(*args).split()


def relation_list(rid=None):
    cmd = command('relation-list')
    args = []
    if rid:
        args.append('-r')
        args.append(rid)
    return cmd(*args).split()


def config_get(attribute):
    cmd = command('config-get')
    args = [attribute]
    return cmd(*args).strip()


def unit_get(attribute):
    cmd = command('unit-get')
    args = [attribute]
    return cmd(*args).strip()


def open_port(port, protocol="TCP"):
    cmd = command('open-port')
    args = ['{}/{}'.format(port, protocol)]
    cmd(*args)


def close_port(port, protocol="TCP"):
    cmd = command('close-port')
    args = ['{}/{}'.format(port, protocol)]
    cmd(*args)

START = "start"
RESTART = "restart"
STOP = "stop"
RELOAD = "reload"


def service_control(service_name, action):
    cmd = command('service')
    args = [service_name, action]
    try:
        if action == RESTART:
            try:
                cmd(*args)
            except CalledProcessError:
                service_control(service_name, START)
        else:
            cmd(*args)
    except CalledProcessError:
        log("Failed to perform {} on service {}".format(action, service_name))


def configure_source(update=False):
    source = config_get('source')
    if ((source.startswith('ppa:') or
         source.startswith('cloud:') or
         source.startswith('http:'))):
        run('add-apt-repository', source)
    if source.startswith("http:"):
        run('apt-key', 'import', config_get('key'))
    if update:
        run('apt-get', 'update')


def make_charm_config_file(charm_config):
    charm_config_file = tempfile.NamedTemporaryFile()
    charm_config_file.write(yaml.dump(charm_config))
    charm_config_file.flush()
    # The NamedTemporaryFile instance is returned instead of just the name
    # because we want to take advantage of garbage collection-triggered
    # deletion of the temp file when it goes out of scope in the caller.
    return charm_config_file


def unit_info(service_name, item_name, data=None, unit=None):
    if data is None:
        data = yaml.safe_load(juju_status())
    service = data['services'].get(service_name)
    if service is None:
        # XXX 2012-02-08 gmb:
        #     This allows us to cope with the race condition that we
        #     have between deploying a service and having it come up in
        #     `juju status`. We could probably do with cleaning it up so
        #     that it fails a bit more noisily after a while.
        return ''
    units = service['units']
    if unit is not None:
        item = units[unit][item_name]
    else:
        # It might seem odd to sort the units here, but we do it to
        # ensure that when no unit is specified, the first unit for the
        # service (or at least the one with the lowest number) is the
        # one whose data gets returned.
        sorted_unit_names = sorted(units.keys())
        item = units[sorted_unit_names[0]][item_name]
    return item


def get_machine_data():
    return yaml.safe_load(juju_status())['machines']


def wait_for_machine(num_machines=1, timeout=300):
    """Wait `timeout` seconds for `num_machines` machines to come up.

    This wait_for... function can be called by other wait_for functions
    whose timeouts might be too short in situations where only a bare
    Juju setup has been bootstrapped.

    :return: A tuple of (num_machines, time_taken). This is used for
             testing.
    """
    # You may think this is a hack, and you'd be right. The easiest way
    # to tell what environment we're working in (LXC vs EC2) is to check
    # the dns-name of the first machine. If it's localhost we're in LXC
    # and we can just return here.
    if get_machine_data()[0]['dns-name'] == 'localhost':
        return 1, 0
    start_time = time.time()
    while True:
        # Drop the first machine, since it's the Zookeeper and that's
        # not a machine that we need to wait for. This will only work
        # for EC2 environments, which is why we return early above if
        # we're in LXC.
        machine_data = get_machine_data()
        non_zookeeper_machines = [
            machine_data[key] for key in machine_data.keys()[1:]]
        if len(non_zookeeper_machines) >= num_machines:
            all_machines_running = True
            for machine in non_zookeeper_machines:
                if machine.get('instance-state') != 'running':
                    all_machines_running = False
                    break
            if all_machines_running:
                break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for service to start')
        time.sleep(SLEEP_AMOUNT)
    return num_machines, time.time() - start_time


def wait_for_unit(service_name, timeout=480):
    """Wait `timeout` seconds for a given service name to come up."""
    wait_for_machine(num_machines=1)
    start_time = time.time()
    while True:
        state = unit_info(service_name, 'agent-state')
        if 'error' in state or state == 'started':
            break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for service to start')
        time.sleep(SLEEP_AMOUNT)
    if state != 'started':
        raise RuntimeError('unit did not start, agent-state: ' + state)


def wait_for_relation(service_name, relation_name, timeout=120):
    """Wait `timeout` seconds for a given relation to come up."""
    start_time = time.time()
    while True:
        relation = unit_info(service_name, 'relations').get(relation_name)
        if relation is not None and relation['state'] == 'up':
            break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for relation to be up')
        time.sleep(SLEEP_AMOUNT)


def wait_for_page_contents(url, contents, timeout=120, validate=None):
    if validate is None:
        validate = operator.contains
    start_time = time.time()
    while True:
        try:
            stream = urllib2.urlopen(url)
        except (urllib2.HTTPError, urllib2.URLError):
            pass
        else:
            page = stream.read()
            if validate(page, contents):
                return page
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for contents of ' + url)
        time.sleep(SLEEP_AMOUNT)
