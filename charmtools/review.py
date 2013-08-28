#!/usr/bin/python
#
#    review - adds review comment to charm bug
#
#    Copyright (C) 2011  Canonical Ltd.
#    Author: Mark Mims <mark.mims@canonical.com>
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

import argparse
import logging
import sys

from launchpadlib.launchpad import Launchpad


def parse_options():
    parser = argparse.ArgumentParser(
        description="Review a charm by adding a comment to the corresponding"
        " charm bug.  The review comment can be passed as a --message"
        " arg or via stdin")

    parser.add_argument('bug_id',
                        help='The launchpad bug for the charm being reviewed.')

    parser.add_argument(
        '--message', '-m',
        help='The review text to add as a comment to the bug.')

    parser.add_argument(
        '--yes', '-y', dest="skip_prompt", default=False, action='store_true',
        help='do not prompt me... just do it.')

    parser.add_argument(
        '--verbose', '-v', default=False, action='store_true',
        help='show debug logging?')

    parser.add_argument(
        '--lp-instance', '-t', dest='lp_instance', default='production',
        help="The Launchpad instance to use. Defaults to production, but "
        "staging' or 'qastaging' might be used for testing.")

    return parser.parse_args()


def log_level(verbose):
    if verbose:
        return logging.DEBUG
    else:
        return logging.WARNING


def get_message_from_stdin():
    stream = sys.stdin
    text = stream.read()
    sys.stdin = open('/dev/tty')  # 'reset' stdin to prompt if necessary
    return text


def get_message(message):
    if message:
        return message
    else:
        return get_message_from_stdin()


def prompt_to_continue(bug_id):
    logging.debug("prompting")
    ans = raw_input("Really add this comment to launchpad bug #%s? y/[n] "
                    % bug_id)
    return ans.strip().lower().startswith('y')


def main():
    args = parse_options()
    logging.basicConfig(level=log_level(args.verbose),
                        format='%(levelname)s:%(message)s')

    review_message = get_message(args.message)  # before connecting to lp

    logging.debug('login with %s launchpad:', args.lp_instance)
    lp = Launchpad.login_with('charm-pilot', args.lp_instance)

    bug_id = args.bug_id
    logging.debug('find bug %s:', bug_id)
    bug = lp.bugs[bug_id]

    if bug:
        logging.debug('found bug')

        if args.skip_prompt or prompt_to_continue(bug_id):
            logging.debug('adding comment')
            # TODO check return or catch exception
            bug.newMessage(content=review_message)
        else:
            logging.debug('not adding comment')

    else:
        logging.error("no bug: %s", bug_id)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
