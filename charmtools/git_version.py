#!/usr/bin/env python

from __future__ import print_function

import os
import sys
import json
import argparse
from subprocess import check_output, CalledProcessError
from pkg_resources import parse_version


git_cmd = ['git', 'describe', '--tags', '--long']
version_filename = os.path.join(os.path.dirname(__file__), '..', 'VERSION')


def get_version_info():
    try:
        version, gitn, gitsha = check_output(git_cmd).strip().rsplit('-', 2)
        if version.startswith('v'):
            version = version[1:]
        snaprev = os.environ.get('SNAP_REVISION', None)
        version_info = {
            'version': version,
            'snap': '+snap_{}'.format(snaprev) if snaprev else '',
            'git': '+git_{}@{}'.format(gitn, gitsha),
            'gitn': int(gitn),
        }
    except CalledProcessError:
        # git info not available; try to find cached version
        try:
            with open(version_filename, 'r') as fh:
                version_info = json.load(fh)
        except (OSError, IOError):
            print("Unable to determine version", file=sys.stderr)
            version_info = {
                'version': '0.0.0',
                'snap': '',
                'git': '',
                'gitn': 0,
            }

    pv = parse_version(version_info['version'])
    version_info['pre_release'] = pv.is_prerelease

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

    with open(version_filename, 'w') as fh:
        # cache version info in case git info is unavailable
        json.dump(version_info, fh)

    pre_release = version_info['pre_release'] or version_info['gitn']
    if args.format == 'long' or (args.format == 'default' and pre_release):
        print('{version}{git}'.format(**version_info))
    else:
        print(version_info['version'])
