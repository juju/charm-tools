#!/usr/bin/env python

import os
import sys
import uuid
import MySQLdb
from charmhelpers.core.hookenv import (
    log,
    relations_of_type,
    Hooks, UnregisteredHookError
)
from charmhelpers.contrib.charmsupport.nrpe import NRPE
from common import get_db_cursor


hooks = Hooks()


def nagios_password():
    PASSFILE = os.path.join('/var', 'lib', 'mysql', 'nagios.passwd')
    if not os.path.isfile(PASSFILE):
        password = str(uuid.uuid4())
        with open(PASSFILE, 'w') as f:
            f.write(password)
        os.chmod(PASSFILE, 0600)
    else:
        with open(PASSFILE, 'r') as rpw:
            password = rpw.read()
    return password


def add_nagios_user():
    c = get_db_cursor()
    if c.execute("SELECT User from mysql.user where User='nagios'"):
        log('User nagios already exists, skipping')
    else:
        log('Creating "nagios" database user')
        password = nagios_password()
        c.execute("CREATE USER 'nagios'@'localhost' IDENTIFIED BY '{}'"
                  "".format(password))

    try:
        c.execute("SHOW GRANTS FOR 'nagios'@'localhost'")
        grants = [i[0] for i in c.fetchall()]
    except MySQLdb.OperationalError:
        grants = []

    for grant in grants:
        if "GRANT PROCESS ON *.*" in grant:
            log('User already has permissions, skipping')
            c.close()
            return
    log('Granting "PROCESS" privilege to nagios user')
    c.execute("GRANT PROCESS ON *.* TO 'nagios'@'localhost'")
    c.close()


def update_nrpe_checks():
    log('Refreshing nrpe checks')
    # Find out if nrpe set nagios_hostname
    hostname = None
    for rel in relations_of_type('nrpe-external-master'):
        if 'nagios_hostname' in rel:
            hostname = rel['nagios_hostname']
            break
    nrpe = NRPE(hostname=hostname)
    nrpe.add_check(
        shortname='mysql_proc',
        description='Check MySQL process',
        check_cmd='check_procs -c 1:1 -C mysqld'
    )
    nrpe.add_check(
        shortname='mysql',
        description='Check MySQL connectivity',
        check_cmd='check_mysql -u nagios -p {}'.format(nagios_password())
    )
    nrpe.write()


@hooks.hook('nrpe-external-master-relation-changed')
@hooks.hook('nrpe-external-master-relation-joined')
def nrpe_relation():
    add_nagios_user()
    update_nrpe_checks()


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
