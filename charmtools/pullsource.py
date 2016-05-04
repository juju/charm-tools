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

 - For charms, $JUJU_REPOSITORY
 - For layers, $LAYER_PATH
 - For interfaces, $INTERFACE_PATH

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

from . import utils
from .build import fetchers
from fetchers import (
    CharmstoreDownloader,
    FETCHERS,
    get,
)


log = logging.getLogger(__name__)

LAYER_PREFIX = 'layer:'
INTERFACE_PREFIX = 'interface:'
CHARM_PREFIX = 'cs:'

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


def download_item(item, dir_):
    series_dir = None

    if item.startswith(LAYER_PREFIX):
        dir_ = dir_ or os.environ.get('LAYER_PATH')
        name = item[len(LAYER_PREFIX):]
    elif item.startswith(INTERFACE_PREFIX):
        dir_ = dir_ or os.environ.get('INTERFACE_PATH')
        name = item[len(INTERFACE_PREFIX):]
    else:
        dir_ = dir_ or os.environ.get('JUJU_REPOSITORY')
        if not item.startswith(CHARM_PREFIX):
            item = CHARM_PREFIX + item

        url_parts = item[len(CHARM_PREFIX):].split('/')
        name = url_parts[-1]
        if len(url_parts) == 2 and not url_parts[0].startswith('~'):
            series_dir = url_parts[0]
        elif len(url_parts) == 3:
            series_dir = url_parts[1]

    dir_ = dir_ or os.getcwd()
    dir_ = os.path.abspath(os.path.expanduser(dir_))

    # Create series dir if we need to
    if series_dir:
        series_path = os.path.join(dir_, series_dir)
        if not os.path.exists(series_path):
            os.mkdir(series_path)
        dir_ = series_path

    # Abort if destination dir already exists
    final_dest_dir = os.path.join(dir_, name)
    if os.path.exists(final_dest_dir):
        return "{}: {}".format(ERR_DIR_EXISTS, final_dest_dir)

    # Create tempdir for initial download
    tempdir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, tempdir)
    try:
        # Download the item
        fetcher = fetchers.get_fetcher(item)
        download_dir = fetcher.fetch(tempdir)
    except fetchers.FetchError:
        return "Can't find source for {}".format(item)

    # Copy download dir to final destination dir
    shutil.copytree(download_dir, final_dest_dir, symlinks=True)
    print('Downloaded {} to {}'.format(item, final_dest_dir))


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

    return download_item(args.item, args.dir)


if __name__ == "__main__":
    sys.exit(main())
