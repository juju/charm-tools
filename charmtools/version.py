
import pkg_resources
import argparse

from cli import parser_defaults
from charmtools import utils


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description='display tooling version information')
    utils.add_plugin_description(parser)
    parser = parser_defaults(parser)
    args = parser.parse_args(args)

    return args


def charm_version():
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


def main():
    get_args()

    version = pkg_resources.get_distribution("charm-tools").version

    print "charm %s" % charm_version()
    print "charm-tools %s" % version


if __name__ == '__main__':
    main()
