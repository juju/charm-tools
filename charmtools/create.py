#!/usr/bin/python
#
#    create - generate Juju charm from template
#
#    Copyright (C) 2011  Canonical Ltd.
#    Author: Clint Byrum <clint.byrum@canonical.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import sys
import argparse

from charmtools.generators import (
    CharmGenerator,
    CharmGeneratorException,
    get_installed_templates,
)

log = logging.getLogger(__name__)

DEFAULT_TEMPLATE = 'python'


def setup_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'charmname',
        help='Name of charm to create.',
    )
    parser.add_argument(
        'charmhome', nargs='?',
        help='Dir to create charm in. Defaults to CHARM_HOME env var or PWD',
    )
    parser.add_argument(
        '-t', '--template', default=None,
        help='Name of charm template to use; default is ' + DEFAULT_TEMPLATE +
             '. Installed templates: ' + ', '.join(get_installed_templates()),
    )
    parser.add_argument(
        '-a', '--accept-defaults',
        help='Accept all template configuration defaults without prompting.',
        action='store_true', default=False,
    )
    parser.add_argument(
        '-v', '--verbose',
        help='Print debug information',
        action='store_true', default=False,
    )

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()
    args.charmhome = args.charmhome or os.getenv('CHARM_HOME', '.')
    args.config = None

    if args.verbose:
        logging.basicConfig(
            format='%(levelname)s %(filename)s: %(message)s',
            level=logging.DEBUG,
        )
    else:
        logging.basicConfig(
            format='%(levelname)s: %(message)s',
            level=logging.INFO,
        )

    if not args.template:
        log.info(
            "Using default charm template (%s). To select a different "
            "template, use the -t option.", DEFAULT_TEMPLATE)
        args.template = DEFAULT_TEMPLATE

    generator = CharmGenerator(args)
    try:
        generator.create_charm()
    except CharmGeneratorException as e:
        log.error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
