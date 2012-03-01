# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper functions for writing Juju charms in Python."""

__metaclass__ = type
__all__ = [
    'get_config',
    'log',
    'log_entry',
    'log_exit',
    'relation_get',
    'relation_set',
    'unit_info',
    ]

from collections import namedtuple
import json
import operator
from shelltoolbox import (
    command,
    run,
    script_name,
    )
import tempfile
import time
import urllib2
import yaml


Env = namedtuple('Env', 'uid gid home')

log = command('juju-log')


def log_entry():
    log("--> Entering {}".format(script_name()))


def log_exit():
    log("<-- Exiting {}".format(script_name()))


def get_config():
    config_get = command('config-get', '--format=json')
    return json.loads(config_get())


def relation_get(*args):
    cmd = command('relation-get')
    return cmd(*args).strip()


def relation_set(**kwargs):
    cmd = command('relation-set')
    args = ['{}={}'.format(k, v) for k, v in kwargs.items()]
    return cmd(*args)


def make_charm_config_file(charm_config):
    charm_config_file = tempfile.NamedTemporaryFile()
    charm_config_file.write(yaml.dump(charm_config))
    charm_config_file.flush()
    # The NamedTemporaryFile instance is returned instead of just the name
    # because we want to take advantage of garbage collection-triggered
    # deletion of the temp file when it goes out of scope in the caller.
    return charm_config_file


def unit_info(service_name, item_name, data=None):
    if data is None:
        data = yaml.safe_load(run('juju', 'status'))
    service = data['services'].get(service_name)
    if service is None:
        # XXX 2012-02-08 gmb:
        #     This allows us to cope with the race condition that we
        #     have between deploying a service and having it come up in
        #     `juju status`. We could probably do with cleaning it up so
        #     that it fails a bit more noisily after a while.
        return ''
    units = service['units']
    item = units.items()[0][1][item_name]
    return item


def get_machine_data():
    return yaml.safe_load(run('juju', 'status'))['machines']


def wait_for_machine(num_machines=1, timeout=300):
    """Wait `timeout` seconds for `num_machines` machines to come up.

    This wait_for... function can be called by other wait_for functions
    whose timeouts might be too short in situations where only a bare
    Juju setup has been bootstrapped.
    """
    # You may think this is a hack, and you'd be right. The easiest way
    # to tell what environment we're working in (LXC vs EC2) is to check
    # the dns-name of the first machine. If it's localhost we're in LXC
    # and we can just return here.
    if get_machine_data()[0]['dns-name'] == 'localhost':
        return
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
                if machine['instance-state'] != 'running':
                    all_machines_running = False
                    break
            if all_machines_running:
                break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for service to start')
        time.sleep(0.1)


def wait_for_unit(service_name, timeout=480):
    """Wait `timeout` seconds for a given service name to come up."""
    wait_for_machine(num_machines=1)
    start_time = time.time()
    while True:
        state = unit_info(service_name, 'state')
        if 'error' in state or state == 'started':
            break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for service to start')
        time.sleep(0.1)
    if state != 'started':
        raise RuntimeError('unit did not start, state: ' + state)


def wait_for_relation(service_name, relation_name, timeout=120):
    """Wait `timeout` seconds for a given relation to come up."""
    start_time = time.time()
    while True:
        relation = unit_info(service_name, 'relations').get(relation_name)
        if relation is not None and relation['state'] == 'up':
            break
        if time.time() - start_time >= timeout:
            raise RuntimeError('timeout waiting for relation to be up')
        time.sleep(0.1)


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
        time.sleep(0.1)
