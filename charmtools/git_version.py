#!/usr/bin/env python

from __future__ import print_function

import argparse
import json
import os
import sys
from subprocess import check_output, CalledProcessError, PIPE
from pkg_resources import parse_version, resource_string, resource_exists


git_cmd = ['git', 'describe', '--tags', '--long']


def _scm_version(name):
    try:
        output = check_output(git_cmd, stderr=PIPE)
        if sys.version_info >= (3, 0):
            output = output.decode('UTF-8')
        version, gitn, gitsha = output.strip().rsplit('-', 2)
        if version.startswith('v'):
            version = version[1:]
        return {
            'version': version,
            'git': '+git-{}-{}'.format(gitn, gitsha),
            'gitn': int(gitn),
        }
    except CalledProcessError:
        print("Unable to determine {} version".format(name), file=sys.stderr)
        return {
            'version': '0.0.0',
            'git': '',
            'gitn': 0,
        }


def _add_pre_rel(version_info):
    pv = parse_version(version_info['version'])
    version_info['pre_release'] = pv.is_prerelease


def _add_snap_rev(version_info):
    # snap rev is not available at build time, so we can never cache it
    snaprev = os.environ.get('SNAP_REVISION', None)
    version_info['snap'] = '+snap-{}'.format(snaprev) if snaprev else ''


def get_version_info():
    if resource_exists(__name__, 'VERSION'):
        res_string = resource_string(__name__, 'VERSION')
        if sys.version_info >= (3, 0):
            res_string = res_string.decode('UTF-8')
        version_info = json.loads(res_string)
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
        version_info = _scm_version('charm-tools')

    _add_pre_rel(version_info)
    _add_snap_rev(version_info)

    return version_info


def _build_charm_version():
    old_dir = os.getcwd()
    os.chdir('../parts/charmstore-client/src')
    try:
        version_info = _scm_version('charmstore-client')
    finally:
        os.chdir(old_dir)

    _add_pre_rel(version_info)
    version_info['snap'] = ''  # no snap rev for charmstore part

    with open('charmstore-client-version', 'w') as fh:
        json.dump(version_info, fh)


def _get_charm_tools_version():
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


def get_args(args=None):
    parser = argparse.ArgumentParser(description='Determine version')
    parser.add_argument('--format', choices=['long', 'short', 'default'],
                        default='default',
                        help="Version format. Long includes git revision "
                             "info. Default uses long if it's a pre-release.")
    parser.add_argument('--build-charm-version', action='store_true')
    args = parser.parse_args(args)

    return args


if __name__ == '__main__':
    args = get_args()
    if args.build_charm_version:
        _build_charm_version()
    else:
        _get_charm_tools_version()
