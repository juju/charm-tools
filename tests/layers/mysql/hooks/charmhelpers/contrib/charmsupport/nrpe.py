"""Compatibility with the nrpe-external-master charm"""
# Copyright 2012 Canonical Ltd.
#
# Authors:
#  Matthew Wedgwood <matthew.wedgwood@canonical.com>

import subprocess
import pwd
import grp
import os
import re
import shlex
import yaml

from charmhelpers.core.hookenv import (
    config,
    local_unit,
    log,
    relation_ids,
    relation_set,
)

from charmhelpers.core.host import service

# This module adds compatibility with the nrpe-external-master and plain nrpe
# subordinate charms. To use it in your charm:
#
# 1. Update metadata.yaml
#
#   provides:
#     (...)
#     nrpe-external-master:
#       interface: nrpe-external-master
#       scope: container
#
#   and/or
#
#   provides:
#     (...)
#     local-monitors:
#       interface: local-monitors
#       scope: container

#
# 2. Add the following to config.yaml
#
#    nagios_context:
#      default: "juju"
#      type: string
#      description: |
#        Used by the nrpe subordinate charms.
#        A string that will be prepended to instance name to set the host name
#        in nagios. So for instance the hostname would be something like:
#            juju-myservice-0
#        If you're running multiple environments with the same services in them
#        this allows you to differentiate between them.
#
# 3. Add custom checks (Nagios plugins) to files/nrpe-external-master
#
# 4. Update your hooks.py with something like this:
#
#    from charmsupport.nrpe import NRPE
#    (...)
#    def update_nrpe_config():
#        nrpe_compat = NRPE()
#        nrpe_compat.add_check(
#            shortname = "myservice",
#            description = "Check MyService",
#            check_cmd = "check_http -w 2 -c 10 http://localhost"
#            )
#        nrpe_compat.add_check(
#            "myservice_other",
#            "Check for widget failures",
#            check_cmd = "/srv/myapp/scripts/widget_check"
#            )
#        nrpe_compat.write()
#
#    def config_changed():
#        (...)
#        update_nrpe_config()
#
#    def nrpe_external_master_relation_changed():
#        update_nrpe_config()
#
#    def local_monitors_relation_changed():
#        update_nrpe_config()
#
# 5. ln -s hooks.py nrpe-external-master-relation-changed
#    ln -s hooks.py local-monitors-relation-changed


class CheckException(Exception):
    pass


class Check(object):
    shortname_re = '[A-Za-z0-9-_]+$'
    service_template = ("""
#---------------------------------------------------
# This file is Juju managed
#---------------------------------------------------
define service {{
    use                             active-service
    host_name                       {nagios_hostname}
    service_description             {nagios_hostname}[{shortname}] """
                        """{description}
    check_command                   check_nrpe!{command}
    servicegroups                   {nagios_servicegroup}
}}
""")

    def __init__(self, shortname, description, check_cmd):
        super(Check, self).__init__()
        # XXX: could be better to calculate this from the service name
        if not re.match(self.shortname_re, shortname):
            raise CheckException("shortname must match {}".format(
                Check.shortname_re))
        self.shortname = shortname
        self.command = "check_{}".format(shortname)
        # Note: a set of invalid characters is defined by the
        # Nagios server config
        # The default is: illegal_object_name_chars=`~!$%^&*"|'<>?,()=
        self.description = description
        self.check_cmd = self._locate_cmd(check_cmd)

    def _locate_cmd(self, check_cmd):
        search_path = (
            '/usr/lib/nagios/plugins',
            '/usr/local/lib/nagios/plugins',
        )
        parts = shlex.split(check_cmd)
        for path in search_path:
            if os.path.exists(os.path.join(path, parts[0])):
                command = os.path.join(path, parts[0])
                if len(parts) > 1:
                    command += " " + " ".join(parts[1:])
                return command
        log('Check command not found: {}'.format(parts[0]))
        return ''

    def write(self, nagios_context, hostname):
        nrpe_check_file = '/etc/nagios/nrpe.d/{}.cfg'.format(
            self.command)
        with open(nrpe_check_file, 'w') as nrpe_check_config:
            nrpe_check_config.write("# check {}\n".format(self.shortname))
            nrpe_check_config.write("command[{}]={}\n".format(
                self.command, self.check_cmd))

        if not os.path.exists(NRPE.nagios_exportdir):
            log('Not writing service config as {} is not accessible'.format(
                NRPE.nagios_exportdir))
        else:
            self.write_service_config(nagios_context, hostname)

    def write_service_config(self, nagios_context, hostname):
        for f in os.listdir(NRPE.nagios_exportdir):
            if re.search('.*{}.cfg'.format(self.command), f):
                os.remove(os.path.join(NRPE.nagios_exportdir, f))

        templ_vars = {
            'nagios_hostname': hostname,
            'nagios_servicegroup': nagios_context,
            'description': self.description,
            'shortname': self.shortname,
            'command': self.command,
        }
        nrpe_service_text = Check.service_template.format(**templ_vars)
        nrpe_service_file = '{}/service__{}_{}.cfg'.format(
            NRPE.nagios_exportdir, hostname, self.command)
        with open(nrpe_service_file, 'w') as nrpe_service_config:
            nrpe_service_config.write(str(nrpe_service_text))

    def run(self):
        subprocess.call(self.check_cmd)


class NRPE(object):
    nagios_logdir = '/var/log/nagios'
    nagios_exportdir = '/var/lib/nagios/export'
    nrpe_confdir = '/etc/nagios/nrpe.d'

    def __init__(self, hostname=None):
        super(NRPE, self).__init__()
        self.config = config()
        self.nagios_context = self.config['nagios_context']
        self.unit_name = local_unit().replace('/', '-')
        if hostname:
            self.hostname = hostname
        else:
            self.hostname = "{}-{}".format(self.nagios_context, self.unit_name)
        self.checks = []

    def add_check(self, *args, **kwargs):
        self.checks.append(Check(*args, **kwargs))

    def write(self):
        try:
            nagios_uid = pwd.getpwnam('nagios').pw_uid
            nagios_gid = grp.getgrnam('nagios').gr_gid
        except:
            log("Nagios user not set up, nrpe checks not updated")
            return

        if not os.path.exists(NRPE.nagios_logdir):
            os.mkdir(NRPE.nagios_logdir)
            os.chown(NRPE.nagios_logdir, nagios_uid, nagios_gid)

        nrpe_monitors = {}
        monitors = {"monitors": {"remote": {"nrpe": nrpe_monitors}}}
        for nrpecheck in self.checks:
            nrpecheck.write(self.nagios_context, self.hostname)
            nrpe_monitors[nrpecheck.shortname] = {
                "command": nrpecheck.command,
            }

        service('restart', 'nagios-nrpe-server')

        for rid in relation_ids("local-monitors"):
            relation_set(relation_id=rid, monitors=yaml.dump(monitors))
