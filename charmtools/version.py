from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import json
import argparse
from pkg_resources import resource_string, resource_exists

from charmtools.cli import parser_defaults
from charmtools import utils
from vergit import format_version


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description='display tooling version information')
    parser.add_argument('--format',
                        choices=['long', 'short', 'default', 'json'],
                        default='default',
                        help="Version format. Long includes git revision "
                             "info. Default uses long if it's a pre-release.")
    utils.add_plugin_description(parser)
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def _add_snap_rev(version_info):
    if 'SNAP_REVISION' in os.environ:
        version_info['snap'] = '+snap-{}'.format(os.environ['SNAP_REVISION'])
    return version_info


def cached_charmstore_client_version():
    if 'SNAP' in os.environ:
        cscv = os.path.join(os.environ['SNAP'], 'charmstore-client-version')
        if not os.path.exists(cscv):
            return {'version': 'unavailable', 'git': ''}
        with open(cscv) as f:
            res_string = f.read().strip()
        return _add_snap_rev(json.loads(res_string))
    try:
        from apt.cache import Cache
        charm_vers = Cache()['charm'].versions
        for v in charm_vers:
            if v.is_installed:
                charm_ver = v.version
                break
        else:
            charm_ver = 'unavailable'
    except ImportError:
        charm_ver = 'unavailable'
    except:
        charm_ver = 'error'

    return _add_snap_rev({'version': charm_ver})


def cached_charm_tools_version():
    ctv = os.path.join(os.environ.get('SNAP', ''), 'charm-tools-version')
    if os.path.exists(ctv):
        with open(ctv) as f:
            res_string = f.read().strip()
        return _add_snap_rev(json.loads(res_string))
    if resource_exists(__name__, 'VERSION'):
        res_string = resource_string(__name__, 'VERSION')
        if sys.version_info >= (3, 0):
            res_string = res_string.decode('UTF-8')
        return _add_snap_rev(json.loads(res_string))
    if os.environ.get('SNAPCRAFT_PROJECT_VERSION', 'git') != 'git':
        version_parts = os.environ['SNAPCRAFT_PROJECT_VERSION'].split('+')
        git = ''
        gitn = 0
        if len(version_parts) > 1:
            git = version_parts[1]
            gitn = int(git.split('-')[1])
        return _add_snap_rev({
            'version': version_parts[0],
            'git': '+{}'.format(git),
            'gitn': gitn,
        })
    return {'version': 'unavailable'}


def main():
    args = get_args()

    if args.format == 'json':
        print(json.dumps({
            'charmstore-client': cached_charmstore_client_version(),
            'charm-tools': cached_charm_tools_version(),
        }))
    else:
        print("charmstore-client {}".format(
            format_version(cached_charmstore_client_version(), args.format)))
        print("charm-tools {}".format(
            format_version(cached_charm_tools_version(), args.format)))


if __name__ == '__main__':
    main()
