#!/usr/bin/env python

import sys

import common
from charmhelpers.core import hookenv, host


hooks = hookenv.Hooks()
mountpoint = '/srv/mysql'


@hooks.hook('data-relation-joined', 'data-relation-changed')
def data_relation():
    if hookenv.relation_get('mountpoint') == mountpoint:
        # Other side of relation is ready
        common.migrate_to_mount(mountpoint)
    else:
        # Other side not ready yet, provide mountpoint
        hookenv.log('Requesting storage for {}'.format(mountpoint))
        hookenv.relation_set(mountpoint=mountpoint)


@hooks.hook('data-relation-departed', 'data-relation-broken')
def data_relation_gone():
    hookenv.log('Data relation no longer present, stopping MysQL.')
    host.service_stop('mysql')


if __name__ == '__main__':
    hooks.execute(sys.argv)
