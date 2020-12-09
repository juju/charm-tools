#!/usr/bin/python

#    Copyright (C) 2019  Canonical Ltd.
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

from __future__ import absolute_import

import argparse
import json
import os
import sys
from subprocess import run, PIPE


def _fail(msg, debug_msg=None, show_debug=False):
    if show_debug:
        if isinstance(debug_msg, bytes):
            debug_msg = debug_msg.decode('utf8')
        print(debug_msg, file=sys.stderr)
    print(msg, file=sys.stderr)
    sys.exit(1)


def _bin(filename):
    return os.path.join(os.environ['SNAP'], 'bin', filename)


def _url(charm_id):
    charm_id = charm_id[len('cs:'):]
    return f"https://api.jujucharms.com/charmstore/v5/{charm_id}/promulgate"


def promulgate():
    parser = argparse.ArgumentParser(
        description='Promote a charm from a personal namespace to the flat, '
                    'top-level namespace')
    parser.add_argument('charm_id',
                        help='Charm store URL of charm (e.g., cs:~user/charm)')
    parser.add_argument('--debug', action='store_true',
                        help='Output debug information')
    args = parser.parse_args()
    charm_id = args.charm_id

    if not charm_id.startswith('cs:'):
        _fail('Must provide a fully-qualified charm ID starting with "cs:"')
    if not charm_id.startswith('cs:~'):
        _fail('Must provide a namespaced charm ID')

    charm_show = run([_bin('wrappers/charm'), 'show',
                      charm_id, '--format=json'],
                     stdout=PIPE, stderr=PIPE)
    if charm_show.returncode != 0:
        _fail(f'{charm_id} is not released to stable, or cannot be read',
              charm_show.stdout + charm_show.stderr, args.debug)
    charm_info = json.loads(charm_show.stdout.decode('utf8'))
    if charm_info['promulgated']['Promulgated']:
        _fail(f'{charm_id} is already promulgated',
              charm_info['promulgated'], args.debug)
    if 'everyone' not in charm_info['perm']['Read']:
        _fail(f'{charm_id} is not readable by "everyone"',
              charm_info['perm']['Read'], args.debug)

    promulgated_id = 'cs:' + charm_id.split('/', 1)[-1]
    promulgated_show = run([_bin('wrappers/charm'), 'show',
                            promulgated_id, '--format=json'],
                           stdout=PIPE, stderr=PIPE)
    if promulgated_show.returncode == 0:
        promulgated_info = json.loads(promulgated_show.stdout.decode('utf8'))
        owner = promulgated_info['owner']['User']
        _fail(f'{promulgated_id} is already owned by {owner}; '
              f'you will need to unpromulgate first to change owner')

    res = run([_bin('bhttp'), 'put', '-j', _url(charm_id),
               'Promulgated:=true'])
    if res.returncode != 0:
        sys.exit(res.returncode)
    print(f'{charm_id} promulgated to {promulgated_id}')

    writers = [writer
               for writer in charm_info['perm']['Write']
               if writer not in ('charmers', 'everyone')]
    if not writers:
        _fail('Unable to determine non-charmers writer to grant; '
              'check and correct perms manually')
    for writer in writers:
        res = run([_bin('wrappers/charm'), 'grant',
                   promulgated_id, '--acl=write', writer],
                  stdout=PIPE, stderr=PIPE)
        if res.returncode != 0:
            _fail(f'Failed to grant write on {promulgated_id} to {writer}',
                  res.stdout + res.stderr, args.debug)
    print(f'Granted write on {promulgated_id} to: {", ".join(writers)}')


def unpromulgate():
    parser = argparse.ArgumentParser(
        description='Remove a charm from the flat, top-level namespace')
    parser.add_argument('charm_id',
                        help='Charm store URL of charm (e.g., cs:~user/charm)')
    parser.add_argument('--debug', action='store_true',
                        help='Output debug information')
    args = parser.parse_args()
    charm_id = args.charm_id

    if not charm_id.startswith('cs:'):
        _fail('Must provide a fully-qualified charm ID starting with "cs:"')
    if charm_id.startswith('cs:~'):
        owner, charm_id = charm_id[len('cs:~'):].split('/', 1)
        charm_id = 'cs:' + charm_id
    else:
        owner = None

    charm_show = run([_bin('wrappers/charm'), 'show',
                      charm_id, '--format=json'],
                     stdout=PIPE, stderr=PIPE)
    if charm_show.returncode != 0:
        _fail(f'{charm_id} is not promulgated',
              charm_show.stdout + charm_show.stderr, args.debug)

    charm_info = json.loads(charm_show.stdout.decode('utf8'))
    if owner is not None and charm_info['owner']['User'] != owner:
        _fail(f'{charm_id} is not owned by {owner}',
              charm_info['owner'], args.debug)

    res = run([_bin('bhttp'), 'put', '-j', _url(charm_id),
               'Promulgated:=false'])
    if res.returncode != 0:
        sys.exit(1)
    print(f'{charm_id} unpromulgated')
