from __future__ import print_function
from __future__ import absolute_import

import os
import pkg_resources
import argparse

from charmtools.cli import parser_defaults
from charmtools import utils
from charmtools.git_version import get_version_info


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description='display tooling version information')
    parser.add_argument('--format', choices=['long', 'short', 'default'],
                        default='default',
                        help="Version format. Long includes git revision "
                             "info. Default uses long if it's a pre-release.")
    utils.add_plugin_description(parser)
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def charm_version():
    if 'SNAP' in os.environ:
        cscv = os.path.join(os.environ['SNAP'], 'charmstore-client-version')
        if os.path.exists(cscv):
            with open(cscv) as f:
                charm_ver = f.read().strip()
            return charm_ver
    try:
        from apt.cache import Cache
        charm_vers = Cache()['charm'].versions
        for v in charm_vers:
            if v.is_installed:
                charm_ver = v.version
                break
    except ImportError:
        charm_ver = 'unavailable'
    except:
        charm_ver = 'error'

    return charm_ver


def charm_tools_version(ver_format):
    version_info = get_version_info()
    pre_release = version_info['pre_release'] or version_info['gitn']
    if ver_format == 'long' or (ver_format == 'default' and pre_release):
        return '{version}{snap}{git}'.format(**version_info)
    else:
        return version_info['version']


def main():
    args = get_args()

    print("charm %s" % charm_version())
    print("charm-tools %s" % charm_tools_version(args.format))


if __name__ == '__main__':
    main()
