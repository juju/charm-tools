#!/usr/bin/env python

from __future__ import print_function

import argparse
import os
import sys
import json
from subprocess import check_output, CalledProcessError, PIPE
from pkg_resources import parse_version


git_cmd = ['git', 'describe', '--tags', '--long']


def _scm_version(repo_path):
    old_dir = os.getcwd()
    os.chdir(repo_path)
    try:
        output = check_output(git_cmd, stderr=PIPE)
        if sys.version_info >= (3, 0):
            output = output.decode('UTF-8')
        version, gitn, gitsha = output.strip().rsplit('-', 2)
        if version.startswith('v'):
            version = version[1:]
        pv = parse_version(version)
        return {
            'version': version,
            'git': '+git-{}-{}'.format(gitn, gitsha),
            'gitn': int(gitn),
            'pre_release':  pv.is_prerelease,
        }
    except CalledProcessError:
        return {'version': 'unknown'}
    finally:
        os.chdir(old_dir)


def format_version(version_info, ver_format):
    if ver_format == 'json':
        return json.dumps(version_info)
    pre_release = version_info.get('pre_release') or version_info.get('gitn')
    if ver_format == 'long' or (ver_format == 'default' and pre_release):
        return '{version}{snap}{git}'.format(version=version_info['version'],
                                             snap=version_info.get('snap', ''),
                                             git=version_info.get('git', ''))
    else:
        return version_info['version']


def get_args(args=None):
    parser = argparse.ArgumentParser(description='Determine version from git')
    parser.add_argument('path', nargs='?', default='.',
                        help='Path of repo to inspect')
    parser.add_argument('--format',
                        choices=['long', 'short', 'default', 'json'],
                        default='default',
                        help="Version format. Long includes git revision "
                             "info. Default uses long if it's a pre-release.")
    args = parser.parse_args(args)

    return args


if __name__ == '__main__':
    args = get_args()
    print(format_version(_scm_version(args.path), args.format))
