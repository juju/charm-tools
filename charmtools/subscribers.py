#!/usr/bin/python
#
#    subscribers - list and manipulate charm subscribers
#
#    Copyright (C) 2012  Canonical Ltd.
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
#
import os
import sys
import yaml
import argparse
import logging
from logging import warn, info, debug

from launchpadlib import launchpad


def setup_parser():
    parser = argparse.ArgumentParser(
        description="""Prints out a report and optionally corrects found
        instances where maintainers of charms are not subscribed to bugs
        on their charm in launchpad.

        Users will need all charms they are interested in checking locally
        in the specified repository so that metadata.yaml can be inspected
        to find the maintainer.""")
    parser.add_argument('--subscribed', default=False, action='store_true',
                        help='Show maintainers who are properly subscribed '
                        'instead of unsubscribed')
    parser.add_argument('--repository', default=None, type=str,
                        help='Repository to look for charms in. Defaults to '
                        '$JUJU_REPOSITORY or getcwd')
    parser.add_argument('--quiet', default=False, action='store_true',
                        help='Hide everything except maintainer subscription '
                        'lists.')
    parser.add_argument('--series', '-s', default=None,
                        help='Which series of the charm store to run against. '
                        'Defaults to current dev focus')
    parser.add_argument('--maintainer', default=None,
                        help='Limit output to this maintainer\'s charms only.')
    parser.add_argument('--log-priority', default='WARNING')
    parser.add_argument('--launchpad-instance', default='production')
    parser.add_argument('--fix-unsubscribed', default=False,
                        action='store_true', help='Add a bug subscription for '
                        'any unsubscribed maintainers. Requires --maintainer')
    parser.add_argument('--force-fix-all', default=False, action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('charms', default=[], nargs='*',
                        help='Charms to check for subscriptions')

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if args.repository is None:
        repository = os.environ.get('JUJU_REPOSITORY', os.getcwd())
    else:
        repository = args.repository

    if args.log_priority == 'WARNING':
        log_prio = logging.WARNING
    elif args.log_priority == 'INFO':
        log_prio = logging.INFO
    elif args.log_priority == 'CRITICAL':
        log_prio = logging.CRITICAL
    elif args.log_priority == 'INFO':
        log_prio = logging.INFO
    elif args.log_priority == 'DEBUG':
        log_prio = logging.DEBUG
    else:
        log_prio = logging.DEBUG

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        level=log_prio)

    if args.quiet:
        logging.disable(logging.WARNING)

    if args.maintainer is None and args.fix_unsubscribed:
        warn('Running --fix-unsubscribed and without --maintainer is against'
             ' policy.')
        if not args.force_fix_all:
            warn('Use --force-fix-all to override policy')
            sys.exit(1)
        else:
            warn('--force-fix-all passed, continuing')

    app_name = 'Charm Tools - subscribers'
    home_dir = os.environ.get('HOME', os.path.expanduser('~'))
    launchpadlib_dir = os.path.join(home_dir, '.cache', 'launchpadlib')

    if args.fix_unsubscribed:
        login = launchpad.Launchpad.login_with
    else:
        login = launchpad.Launchpad.login_anonymously

    lp = login(app_name, args.launchpad_instance,
               version='devel', launchpadlib_dir=launchpadlib_dir)

    charmdistro = lp.distributions['charms']

    if args.series:
        current_series = args.series
    else:
        current_series = str(charmdistro.current_series).split('/').pop()

    charms = []
    if len(args.charms):
        for charm_name in args.charms:
            # XXX Is this line really neccesary?
            charmdistro.getSourcePackage(name=charm_name)
            charms.append(charm_name)
    else:
        branches = charmdistro.getBranchTips()
        for branch in branches:
            try:
                branch_series = str(branch[2][0]).split('/')[0]
                charm_name = str(branch[0]).split('/')[3]
            except IndexError:
                continue
            if branch_series != current_series:
                continue
            charms.append(charm_name)

    for charm_name in charms:
        try:
            with open('%s/%s/%s/metadata.yaml' % (repository, current_series,
                                                  charm_name)) as mdata:
                mdata_parsed = yaml.safe_load(mdata)
        except IOError:
            warn('%s/%s has no metadata in charm repo' % (current_series,
                                                          charm_name))
            continue
        try:
            maintainers = mdata_parsed['maintainer']
        except KeyError:
            warn('%s has no maintainer' % charm_name)
            continue

        if type(maintainers) == str:
            maintainers = [maintainers]

        if args.maintainer is not None:
            if args.maintainer not in maintainers:
                maints_by_email = [m.split('<')[1].split('>')[0]
                                   for m in maintainers]
                if args.maintainer not in maints_by_email:
                    debug('%s not in maintainer list %s' % (args.maintainer,
                                                            maintainers))
                    continue

        for maintainer in maintainers:
            maint_email = maintainer.split('<')[1].split('>')[0]
            lp_maintainer = lp.people.getByEmail(email=maint_email)
            if not lp_maintainer:
                warn('%s has no people in launchpad' % maintainer)
                continue
            pkg = charmdistro.getSourcePackage(name=charm_name)
            subscription = pkg.getSubscription(person=lp_maintainer)
            if subscription is not None:
                msg = '%s is subscribed to %s' % (maintainer, charm_name)
                if args.subscribed:
                    print msg
                else:
                    info(msg)
            elif not args.subscribed:
                msg = '%s is not subscribed to %s' % (maintainer, charm_name)
                if args.subscribed:
                    info(msg)
                else:
                    print msg
                if args.fix_unsubscribed:
                    info('adding bug subscription to %s for %s' %
                         (charm_name, maint_email))
                    pkg.addBugSubscription(subscriber=lp_maintainer)
