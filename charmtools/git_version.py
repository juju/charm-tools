#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import json
import argparse
from subprocess import check_output, CalledProcessError, PIPE
from pkg_resources import parse_version, resource_string, resource_exists


git_cmd = ['git', 'describe', '--tags', '--long']


def get_version_info():
    if resource_exists(__name__, 'VERSION'):
        version_info = json.loads(resource_string(__name__, 'VERSION'))
    elif os.environ.get('SNAPCRAFT_PROJECT_VERSION', 'git') != 'git':
        version_parts = os.environ['SNAPCRAFT_PROJECT_VERSION'].split('+')
        git = ''
        gitn = 0
        if len(version_parts) > 1:
            git = version_parts[1]
            gitn = int(git.split('-')[1])
        version_info = {
            'version': version_parts[0],
            'git': '+{}'.format(git),
            'gitn': gitn,
        }
    else:
        try:
            output = check_output(git_cmd, stderr=PIPE)
            version, gitn, gitsha = output.strip().rsplit('-', 2)
            if version.startswith('v'):
                version = version[1:]
            version_info = {
                'version': version,
                'git': '+git-{}-{}'.format(gitn, gitsha),
                'gitn': int(gitn),
            }
        except CalledProcessError:
            print("Unable to determine charm-tools version", file=sys.stderr)
            version_info = {
                'version': '0.0.0',
                'snap': '',
                'git': '',
                'gitn': 0,
            }

    pv = parse_version(version_info['version'])
    version_info['pre_release'] = pv.is_prerelease

    # snap rev is not available at build time, so we can never cache it
    snaprev = os.environ.get('SNAP_REVISION', None)
    version_info['snap'] = '+snap-{}'.format(snaprev) if snaprev else ''

    return version_info


def get_args(args=None):
    parser = argparse.ArgumentParser(description='Determine version')
    parser.add_argument('--format', choices=['long', 'short', 'default'],
                        default='default',
                        help="Version format. Long includes git revision "
                             "info. Default uses long if it's a pre-release.")
    args = parser.parse_args(args)

    return args


if __name__ == '__main__':
    args = get_args()
    version_info = get_version_info()

    version_filename = os.path.join(os.path.dirname(__file__), 'VERSION')
    with open(version_filename, 'w') as fh:
        # cache version info in case git info is unavailable
        json.dump(version_info, fh)

    pre_release = version_info['pre_release'] or version_info['gitn']
    if args.format == 'long' or (args.format == 'default' and pre_release):
        print('{version}{git}'.format(**version_info))
    else:
        print(version_info['version'])
