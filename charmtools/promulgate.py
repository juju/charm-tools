#!/usr/bin/python
#
#    promulgate - makes a charm recipe branch the official one
#
#    Copyright (C) 2011  Canonical Ltd.
#    Author: Francis J. Lacoste <francis.lacoste@canonical.com>
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
import logging
import subprocess

from optparse import OptionParser
from bzrlib import bzrdir

from launchpadlib.launchpad import Launchpad
from lazr.restfulclient.errors import BadRequest, NotFound

DISTRIBUTION = 'charms'
REVIEW_TEAM_NAME = 'charmers'
OFFICIAL_BRANCH_POCKET = 'Release'
OFFICIAL_BRANCH_STATUS = 'Mature'


def parse_options(unprom_opt=True):
    parser = OptionParser(usage='usage: %prog [options] <charm_dir>')

    parser.add_option(
        '-b', '--branch', dest='branch', default=None,
        help='The location of the charm public branch. Will be determined '
        'from the bzr configuration if omitted.')

    parser.add_option(
        '-s', '--series', dest='series', default=None,
        help='The distribution series on which to set the official branch. '
        'Defaults to setting it in the current development series.')

    parser.add_option(
        '-t', '--lp-instance', dest='lp_instance', default='production',
        help="The Launchpad instance to use. Defaults to production, but "
        "staging' or 'qastaging' might be used for testing.")

    parser.add_option(
        '-v', '--verbose', dest='verbose', action='count', default=0,
        help='Increase verbosity level.')

    if unprom_opt:
        parser.add_option(
            '-u', '--unpromulgate', dest='unpromulgate', action='store_true',
            default=False,
            help='Un-promulgate this branch instead of promulgating it')

    parser.add_option(
        '-f', '--force', dest='force', action='store_true', default=False,
        help='Override warnings and errors.  USE WITH EXTREME CARE !!!!')

    parser.add_option(
        '-w', '--ignore-warnings', dest='ignore_warnings', action='store_true',
        default=False,
        help='Promulgate this branch even with warnings from charm proof')

    parser.add_option(
        '-o', '--owner-branch', dest='promulgate_owner_branch',
        action='store_true', default=False,
        help='Promulgate a branch owned by a someone/group other than '
        '~charmers')

    return parser.parse_args()


def log_level(verbose):
    if verbose >= 2:
        return logging.DEBUG
    elif verbose >= 1:
        return logging.INFO
    else:
        return logging.WARNING


def proof_charm(charm_dir, force=False, ignore_warnings=False):
    logging.info("Running charm proof ... ")
    charm_proof = subprocess.call([sys.executable, os.path.join(
                                   os.path.dirname(os.path.realpath(__file__)),
                                   'proof.py'), charm_dir])
    if charm_proof == 1 or charm_proof == 200:
        if force:
            logging.info("force option enabled ... Continuing with errors")
        else:
            sys.exit(1)
    if charm_proof == 100:
        if ignore_warnings:
            logging.info("ignore-warnings enabled ... Continuing with "
                         "warnings")
        elif force:
            logging.info("force option enabled ... Continuing with warnings")
        else:
            sys.exit(charm_proof)
    if charm_proof == 0:
        logging.info("Excellent ... charm proof passed with flying colors")


def charm_name_from_metadata(charm_dir):
    charm_metadata = os.path.join(charm_dir, 'metadata.yaml')
    if not os.access(charm_metadata, os.R_OK):
        logging.error("can't read charm metadata: %s", charm_metadata)

    with open(charm_metadata) as metadata:
        charm = yaml.safe_load(metadata)

    return charm['name']


def find_branch_to_promulgate(lp, charm_dir, branch_url):
    if branch_url is None:
        tree, branch, relpath = bzrdir.BzrDir.open_containing_tree_or_branch(
            charm_dir)
        push_location = branch.get_push_location()
        if push_location is None:
            logging.error("Branch has not been pushed.")
            return 1
        charm_branch = lp.branches.getByUrl(url=push_location)
        if charm_branch is None:
            logging.error("can't determine Launchpad branch from bzr branch")
            return 1
    else:
        charm_branch = lp.branches.getByUrl(url=branch_url)
        if charm_branch is None:
            logging.error("can't find branch on Launchpad: %s", branch_url)
            return 1
    return charm_branch


def get_lp_charm_series(lp, series):
    charm_distro = lp.distributions[DISTRIBUTION]
    if series is None:
        raise ValueError("Series can not be None")
    try:
        charm_series = charm_distro.getSeries(
            name_or_version=series)
    except (BadRequest, NotFound), e:
        # XXX flacoste 2011-06-15 bug=797917
        # Should only be NotFound.
        if e.content.startswith('No such distribution series:'):
            logging.error("can't find series '%s'", series)
            raise
        else:
            raise
    return charm_series


def update_branch_info(charm_branch, branch_status, branch_reviewer):
    logging.info("Setting status of %s to %s", charm_branch.bzr_identity,
                 branch_status)
    charm_branch.lifecycle_status = branch_status

    logging.info("Setting reviewer of %s to %s", charm_branch.bzr_identity,
                 branch_reviewer)
    charm_branch.reviewer = branch_reviewer

    charm_branch.lp_save()


def update_official_charm_branch(lp, series, charm_branch, charm_name):
    charm_series = get_lp_charm_series(lp, series)
    lp_charm = charm_series.getSourcePackage(name=charm_name)
    if charm_branch:
        logging.info('Setting %s as the official branch for %s',
                     charm_branch.bzr_identity,
                     lp_charm.name)
        update_branch_info(charm_branch, OFFICIAL_BRANCH_STATUS,
                           lp.people[REVIEW_TEAM_NAME])
    else:
        logging.info('Removing official branch for %s', lp_charm.name)
    lp_charm.setBranch(branch=charm_branch, pocket=OFFICIAL_BRANCH_POCKET)


def branch_owner(bzr_branch):
    lp_url = bzr_branch.bzr_identity  # TODO this really sucks... better way?
    return lp_url.lstrip('lp:').split('/')[0]


def is_valid_owner(charm_branch, promulgate_owner_branch):
    if charm_branch is None:
        return True
    return promulgate_owner_branch or branch_owner(charm_branch) == '~charmers'


def main_(options, args):
    logging.basicConfig(level=log_level(options.verbose),
                        format='%(levelname)s:%(message)s')

    if len(args):
        charm_dir = args[0]
    else:
        charm_dir = os.getcwd()

    proof_charm(charm_dir, options.force, options.ignore_warnings)

    logging.debug('login with %s launchpad:', options.lp_instance)
    lp = Launchpad.login_with('promulgate', options.lp_instance)

    if options.unpromulgate:
        logging.info('unpromulgating...')
        charm_branch = None  # makes LP delete the source package.
    else:
        logging.info('promulgating...')
        charm_branch = find_branch_to_promulgate(lp, charm_dir, options.branch)

    if not is_valid_owner(charm_branch, options.promulgate_owner_branch):
        logging.error(" Invalid branch owner: %s", branch_owner(charm_branch))
        logging.error(" Branch push location must be owned by '~charmers'\n"
                      "   use `bzr push --remember lp:~charmers/charms/"
                      "<series>/<charm-name>/trunk`\n   or override this "
                      "behavior using the '--owner-branch'"
                      " option")
        return 1

    update_official_charm_branch(lp, options.series, charm_branch,
                                 charm_name_from_metadata(charm_dir))

    return 0


def main():
    options, args = parse_options()
    return main_(options, args)


if __name__ == '__main__':
    sys.exit(main())
