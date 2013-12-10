#!/usr/bin/python

# Copyright (C) 2013 Marco Ceppi <marco@ceppi.net>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import argparse

from Cheetah.template import Template

from cli import parser_defaults
from charms import Charm
from charmworldlib import charm as cwc

TPL_DIR = os.path.join(os.path.abspath(path.dirname(__file__)), 'templates')
TPL = {'deploy': os.path.join(TPL_DIR, 'tests', 'deploy.tpl'),
       'body': os.path.join(TPL_DIR, 'tests', 'body.tpl'),
       'relate': os.path.join(TPL_DIR, 'tests', 'relate.tpl')}


def graph(interface, endpoint, series='precise'):
    matches = {'requires': 'provides', 'provides': 'requires'}
    c = cwc.Charms()
    charms = c.search({matches[endpoint]: interface, 'series': series})

    return charms[0]


def tests(charm_dir, is_bundle=False, debug=False):
    c = Charm(charm_dir)

    interfaces = {}
    deploy = []
    relations = []

    if not c.is_charm():
        raise Exception('Not a Charm')

    mdata = c.metadata()

    for rel_type in ['provides', 'requires']:
        if rel_type in mdata:
            relations[rel_type] = {}
            for rel, data in mdata[rel_type].iteritems():
                iface = data['interface']
                if iface and iface not in relations[rel_type]:
                    r = graph(iface, rel_type)
                    interfaces[rel_type][iface] = r
                    deploy.append(r.url)

                relations.append(['%s:%s' % (mdata['name'], rel), r.name])

    d = Template(file=TPL['deploy'], searchList=[{'services': deploy}])
    s = Template(file=TPL['relate'], searchList=[{'relations': relations}])

    t = Template(file=TPL['body'], searchList=[{'deploy': d, 'relate': s}])

    if not os.path.exists(os.path.join(charm_dir, 'tests')):
        os.mkdir(os.path.join(charm_dir, 'tests'))

    with open(os.path.join(charm_dir, 'tests', '00-autogen'), 'w') as f:
        f.write(t)

    if not os.path.exists(os.path.join(charm_dir, 'tests', '00-setup')):
        with open(os.path.join(charm_dir, 'tests', '00-setup'), 'w') as f:
            f.write("""
#!/bin/bash

add-apt-repository ppa:juju/stable
apt-get update
apt-get install amulet
""")


def parser(args=None):
    parser = argparse.ArgumentParser(
        description='Builds portions of a charm or bundle')
    parser.add_argument('subcommand', choices=['tests'],
                        help='Which type of generator to run')
    parser = parser_defaults(parser)
    return parser.parse_args(args)


def main():
    a = parser()
    if a.subcommand == 'tests':
        tests(os.getcwd(), is_bundle=a.bundle, debug=a.debug)
    else:
        raise Exception('No subcommand found')


if __name__ == '__main__':
    main()
