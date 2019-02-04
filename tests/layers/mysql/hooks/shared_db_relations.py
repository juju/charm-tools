#!/usr/bin/python
#
# Create relations between a shared database to many peers.
# Join does nothing.   Peer requests access to $DATABASE from $REMOTE_HOST.
# It's up to the hooks to ensure database exists, peer has access and
# clean up grants after a broken/departed peer (TODO)
#
# Author: Adam Gandelman <adam.gandelman@canonical.com>

import subprocess
import json
import lib.utils as utils
import lib.cluster_utils as cluster

from common import get_db_helper
from charmhelpers.core import hookenv
from charmhelpers.contrib.network.ip import (
    get_ipv6_addr
)

LEADER_RES = 'res_mysql_vip'


def pwgen():
    return str(subprocess.check_output(['pwgen', '-s', '16'])).strip()


def relation_get():
    return json.loads(subprocess.check_output(['relation-get',
                                               '--format',
                                               'json']))


def unit_sorted(units):
    """Return a sorted list of unit names."""
    return sorted(
        units, lambda a, b: cmp(int(a.split('/')[-1]), int(b.split('/')[-1])))


def get_unit_addr(relid, unitid):
    return hookenv.relation_get(attribute='private-address',
                                unit=unitid,
                                rid=relid)


def shared_db_changed():
    if not cluster.eligible_leader(LEADER_RES):
        utils.juju_log('INFO',
                       'MySQL service is peered, bailing shared-db relation'
                       ' as this service unit is not the leader')
        return

    if utils.config_get('prefer-ipv6'):
        local_hostname = get_ipv6_addr(exc_list=[utils.config_get('vip')])[0]
    else:
        local_hostname = utils.unit_get('private-address')

    settings = relation_get()
    singleset = set([
        'database',
        'username',
        'hostname'])

    db_helper = get_db_helper()

    if singleset.issubset(settings):
        # Process a single database configuration
        hostname = settings['hostname']
        database = settings['database']
        username = settings['username']

        # Hostname can be json-encoded list of hostnames
        try:
            hostname = json.loads(hostname)
        except ValueError:
            hostname = [hostname]

        for host in hostname:
            password = db_helper.configure_db(host, database, username)

        allowed_units = db_helper.get_allowed_units(database, username)
        allowed_units = unit_sorted(allowed_units)
        allowed_units = ' '.join(allowed_units)

        if cluster.is_clustered():
            db_host = utils.config_get("vip")
        else:
            db_host = local_hostname

        utils.relation_set(db_host=db_host,
                           password=password,
                           allowed_units=allowed_units)
    else:
        # Process multiple database setup requests.
        # from incoming relation data:
        #  nova_database=xxx nova_username=xxx nova_hostname=xxx
        #  quantum_database=xxx quantum_username=xxx quantum_hostname=xxx
        # create
        # {
        #   "nova": {
        #        "username": xxx,
        #        "database": xxx,
        #        "hostname": xxx
        #    },
        #    "quantum": {
        #        "username": xxx,
        #        "database": xxx,
        #        "hostname": xxx
        #    }
        # }
        #
        databases = {}
        for k, v in settings.items():
            db = k.split('_')[0]
            x = '_'.join(k.split('_')[1:])
            if db not in databases:
                databases[db] = {}
            databases[db][x] = v

        return_data = {}
        for db in databases:
            if singleset.issubset(databases[db]):
                database = databases[db]['database']
                hostname = databases[db]['hostname']
                username = databases[db]['username']

                try:
                    # Can be json-encoded list of hostnames
                    hostname = json.loads(hostname)
                except ValueError:
                    # Otherwise expected to be single hostname
                    hostname = [hostname]

                for host in hostname:
                    password = db_helper.configure_db(host, database, username)

                a_units = db_helper.get_allowed_units(database, username)
                a_units = ' '.join(unit_sorted(a_units))
                return_data['%s_allowed_units' % (db)] = a_units

                return_data['%s_password' % (db)] = password

        if len(return_data) > 0:
            utils.relation_set(**return_data)
        if not cluster.is_clustered():
            utils.relation_set(db_host=local_hostname)
        else:
            utils.relation_set(db_host=utils.config_get("vip"))


hooks = {"shared-db-relation-changed": shared_db_changed}

utils.do_hooks(hooks)
