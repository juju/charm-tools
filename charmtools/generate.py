#!/usr/bin/python

from __future__ import absolute_import

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
import shutil
import argparse

from Cheetah.Template import Template

from charmtools.cli import parser_defaults
from charmtools.charms import Charm
from charmstore import CharmStore
from charmstore.error import CharmNotFound
import charmtools.utils as utils

TPL_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'templates')
CHARM_TPL = os.path.join(TPL_DIR, 'charm')


def graph(interface, endpoint, series='trusty'):
    matches = {
        'requires': 'provides',
        'provides': 'requires',
    }
    match = matches[endpoint]
    c = CharmStore()
    try:
        charms = getattr(c, match)(interface)
    except CharmNotFound:
        return None
    charms = [c for c in charms if c.series == series]
    if charms:
        return charms[0]
    else:
        return None


def copy_file(tpl_file, charm_dir, is_bundle=False, debug=False):
    c = Charm(charm_dir)

    if not c.is_charm():
        raise Exception('%s is not a charm' % charm_dir)

    shutil.copy(os.path.join(CHARM_TPL, tpl_file), charm_dir)


def tests(charm_dir, is_bundle=False, debug=False, series='trusty'):
    c = Charm(charm_dir)

    if not c.is_charm():
        raise Exception('Not a Charm')

    mdata = c.metadata()

    interfaces = {}
    deploy = [mdata['name']]
    relations = []

    for rel_type in ['provides', 'requires']:
        if rel_type in mdata:
            interfaces[rel_type] = {}
            for rel, data in mdata[rel_type].items():
                iface = data['interface']
                if iface and iface not in interfaces[rel_type]:
                    r = graph(iface, rel_type, series=series)
                    # If we dont find an interface, do nothing
                    if r is None:
                        continue
                    interfaces[rel_type][iface] = r
                    deploy.append(r.name)

                relations.append(['%s:%s' % (mdata['name'], rel), r.name])

    t = Template(file=os.path.join(TPL_DIR, 'tests', '99-autogen.tpl'),
                 searchList=[{'deploy': deploy, 'relate': relations,
                              'series': series}])

    if not os.path.exists(os.path.join(charm_dir, 'tests')):
        os.mkdir(os.path.join(charm_dir, 'tests'))

    with open(os.path.join(charm_dir, 'tests', '99-autogen'), 'w') as f:
        f.write(str(t))

    if not os.path.exists(os.path.join(charm_dir, 'tests', '00-setup')):
        with open(os.path.join(charm_dir, 'tests', '00-setup'), 'w') as f:
            f.write("""#!/bin/bash

sudo add-apt-repository ppa:juju/stable -y
sudo apt-get update
sudo apt-get install amulet python3-requests -y
""")

    os.chmod(os.path.join(charm_dir, 'tests', '99-autogen'), 0o755)
    os.chmod(os.path.join(charm_dir, 'tests', '00-setup'), 0o755)


def parser(args=None):
    parser = argparse.ArgumentParser(
        description='add icon, readme, or tests to a charm')
    parser.add_argument('subcommand', choices=['tests', 'readme', 'icon'],
                        help='Which type of generator to run')
    utils.add_plugin_description(parser)
    parser = parser_defaults(parser)
    return parser.parse_known_args(args)


def tests_parser(args):
    # This bites, need an argparser experter
    parser = argparse.ArgumentParser(description="add tests to a charm")
    parser.add_argument('--series', '-s', default='trusty',
                        help='Series for the generated test')
    return parser.parse_args(args)


def main():
    a, extra = parser()
    if a.subcommand == 'tests':
        opts = tests_parser(extra)
        tests(os.getcwd(), is_bundle=a.bundle, debug=a.debug,
              series=opts.series)
    elif a.subcommand == 'readme':
        copy_file('README.ex', os.getcwd(), is_bundle=a.bundle, debug=a.debug)
    elif a.subcommand == 'icon':
        copy_file('icon.svg', os.getcwd(), is_bundle=a.bundle, debug=a.debug)
    else:
        raise Exception('No subcommand found')


if __name__ == '__main__':
    main()
