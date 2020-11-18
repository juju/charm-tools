#!/usr/bin/python
#
#    pull-source - Fetch source for charm, layers, and interfaces
#
#    Copyright (C) 2016  Canonical Ltd.
#    Author: Tim Van Steenburgh <tvansteenburgh@gmail.com>
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

"""download the source code for a charm, layer, or interface.

The item to download can be specified using any of the following forms:

 - [cs:]charm
 - [cs:]series/charm
 - [cs:]~user/charm
 - [cs:]~user/series/charm
 - layer:layer-name
 - interface:interface-name

If the item is a layered charm, and the top layer of the charm has a repo
key in layer.yaml, the top layer repo will be cloned. Otherwise, the charm
archive will be downloaded and extracted from the charm store.

If a download directory is not specified, the following environment vars
will be used to determine the download location:

 - For charms, $CHARM_BUILD_DIR/../charms or $JUJU_REPOSITORY (deprecated)
 - For layers, $CHARM_LAYERS_DIR or $LAYER_PATH (deprecated)
 - For interfaces, $CHARM_INTERFACES_DIR or $INTERFACE_PATH (deprecated)

If a download location can not be determined from environment variables,
the current working directory will be used.

The download is aborted if the destination directory already exists.

"""

import argparse
import atexit
import logging
import os
import shutil
import sys
import tempfile
import textwrap

import yaml
from path import Path as path

from charmtools import utils
from charmtools.build import fetchers
from charmtools.fetchers import (
    CharmstoreDownloader,
    FETCHERS,
    get,
)


log = logging.getLogger(__name__)

LAYER_PREFIX = fetchers.LayerFetcher.NAMESPACE + ':'
INTERFACE_PREFIX = fetchers.InterfaceFetcher.NAMESPACE + ':'
CHARM_PREFIX = 'cs:'
CHARM_LAYERS_DIR = os.environ.get(
    fetchers.LayerFetcher.ENVIRON,
    os.environ.get(fetchers.LayerFetcher.OLD_ENVIRON))
CHARM_INTERFACES_DIR = os.environ.get(
    fetchers.InterfaceFetcher.ENVIRON,
    os.environ.get(fetchers.InterfaceFetcher.OLD_ENVIRON))
if 'CHARM_BUILD_DIR' in os.environ:
    CHARM_CHARMS_DIR = os.path.join(
        os.path.dirname(os.environ['CHARM_BUILD_DIR']), 'charms')
else:
    CHARM_CHARMS_DIR = os.environ.get('JUJU_REPOSITORY')

ERR_DIR_EXISTS = "Aborting, destination directory exists"


class CharmstoreRepoDownloader(CharmstoreDownloader):
    """Clones a charm's bzr repo.

    If the a bzr repo is not set, falls back to
    :class:`fetchers.CharmstoreDownloader`.

    """
    EXTRA_INFO_URL = CharmstoreDownloader.STORE_URL + '/meta/extra-info'

    def fetch(self, dir_):
        url = self.EXTRA_INFO_URL.format(self.entity)
        repo_url = get(url).json().get('bzr-url')
        if repo_url:
            try:
                fetcher = fetchers.get_fetcher(repo_url)
            except fetchers.FetchError:
                log.debug(
                    "No fetcher for %s, downloading from charmstore",
                    repo_url)
                return super(CharmstoreRepoDownloader, self).fetch(dir_)
            else:
                return fetcher.fetch(dir_)
        return super(CharmstoreRepoDownloader, self).fetch(dir_)


FETCHERS.insert(0, CharmstoreRepoDownloader)


class CharmstoreLayerDownloader(CharmstoreRepoDownloader):
    """Clones the repo containing the top layer of a charm.

    If the charm is not a layered charm, or the repo for the
    top layer can not be determined, falls back to using
    :class:`CharmstoreRepoDownloader`.

    """
    LAYER_CONFIGS = ['layer.yaml', 'composer.yaml']

    def fetch(self, dir_):
        for cfg in self.LAYER_CONFIGS:
            url = '{}/{}'.format(
                self.ARCHIVE_URL.format(self.entity), cfg)
            result = get(url)
            if not result.ok:
                continue
            repo_url = yaml.safe_load(result.text).get('repo')
            if not repo_url:
                continue
            try:
                fetcher = fetchers.get_fetcher(repo_url)
            except fetchers.FetchError:
                log.debug(
                    'Charm %s has a repo set in %s, but no fetcher could '
                    'be found for the repo (%s).', self.entity, cfg, repo_url)
                break
            else:
                return fetcher.fetch(dir_)
        return super(CharmstoreLayerDownloader, self).fetch(dir_)


FETCHERS.insert(0, CharmstoreLayerDownloader)


def download_item(args):
    series_dir = None

    if args.item.startswith(LAYER_PREFIX):
        dir_ = args.dir or CHARM_LAYERS_DIR
        name = args.item[len(LAYER_PREFIX):]
    elif args.item.startswith(INTERFACE_PREFIX):
        dir_ = args.dir or CHARM_INTERFACES_DIR
        name = args.item[len(INTERFACE_PREFIX):]
    else:
        dir_ = args.dir or CHARM_CHARMS_DIR
        if not args.item.startswith(CHARM_PREFIX):
            args.item = CHARM_PREFIX + args.item

        url_parts = args.item[len(CHARM_PREFIX):].split('/')
        name = url_parts[-1]
        if len(url_parts) == 2 and not url_parts[0].startswith('~'):
            series_dir = url_parts[0]
        elif len(url_parts) == 3:
            series_dir = url_parts[1]

    dir_ = dir_ or os.getcwd()
    dir_ = os.path.abspath(os.path.expanduser(dir_))

    if not os.access(dir_, os.W_OK):
        print('Unable to write to {}'.format(dir_))
        return 200

    # Create series dir if we need to
    if series_dir:
        series_path = os.path.join(dir_, series_dir)
        if not os.path.exists(series_path):
            os.mkdir(series_path)
        dir_ = series_path

    # Abort if destination dir already exists
    final_dest_dir = os.path.join(dir_, name)
    if os.path.exists(final_dest_dir):
        print("{}: {}".format(ERR_DIR_EXISTS, final_dest_dir))
        return 1

    # Create tempdir for initial download
    tempdir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tempdir)
    try:
        # Download the item
        fetcher = fetchers.get_fetcher(args.item)
        download_dir = fetcher.fetch(tempdir)
    except fetchers.FetchError:
        print("Can't find source for {}".format(args.item))
        return 1

    # Copy download dir to final destination dir
    shutil.copytree(download_dir, final_dest_dir, symlinks=True)
    rev = ' (rev: {})'.format(fetcher.revision) if fetcher.revision else ''
    if fetcher.revision:
        rev_file = path(final_dest_dir) / '.pull-source-rev'
        rev_file.write_text(fetcher.revision)
    print('Downloaded {}{} to {}'.format(args.item, rev, final_dest_dir))


def setup_parser():
    parser = argparse.ArgumentParser(
        prog='charm pull-source',
        description=textwrap.dedent(__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'item',
        help='Name of the charm, layer, or interface to download.'
    )
    parser.add_argument(
        'dir', nargs='?',
        help='Directory in which to place the downloaded source.',
    )
    parser.add_argument(
        '-b', '--branch',
        help='Branch to check out after cloning the repo '
             '(before copying any subdir). If not given, '
             'the default branch of the repo will be used.'
    )
    parser.add_argument(
        '-i', '--layer-index',
        help='One or more index URLs used to look up layers, '
             'separated by commas. Can include the token '
             'DEFAULT, which will be replaced by the default '
             'index{} ({}).  E.g.: https://my-site.com/index/,DEFAULT'.format(
                 'es' if len(fetchers.LayerFetcher.LAYER_INDEXES) > 1 else '',
                 ','.join(fetchers.LayerFetcher.LAYER_INDEXES)))
    parser.add_argument(
        '-v', '--verbose',
        help='Show verbose output',
        action='store_true', default=False,
    )
    utils.add_plugin_description(parser)

    return parser


def main():
    parser = setup_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(
            format='%(levelname)s %(filename)s: %(message)s',
            level=logging.DEBUG,
        )
    else:
        logging.basicConfig(
            format='%(levelname)s: %(message)s',
            level=logging.WARN,
        )

    fetchers.LayerFetcher.NO_LOCAL_LAYERS = True
    fetchers.LayerFetcher.set_layer_indexes(args.layer_index)
    fetchers.LayerFetcher.set_branch(args.branch)

    return download_item(args)


if __name__ == "__main__":
    sys.exit(main())
