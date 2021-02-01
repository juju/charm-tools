import os
import json
import logging
import shutil

import requests
from charmtools import fetchers
from charmtools.fetchers import (git,  # noqa
                                 Fetcher,
                                 get_fetcher,
                                 FetchError)

from path import Path as path


log = logging.getLogger(__name__)


class RepoFetcher(fetchers.LocalFetcher):
    @classmethod
    def can_fetch(cls, url):
        search_path = [os.getcwd(), os.environ.get("JUJU_REPOSITORY", ".")]
        cp = os.environ.get("LAYER_PATH")
        if cp:
            search_path.extend(cp.split(":"))
        for part in search_path:
            p = (path(part) / url).normpath()
            if p.exists():
                return dict(path=p)
        return {}


fetchers.FETCHERS.insert(0, RepoFetcher)


class LayerFetcher(fetchers.LocalFetcher):
    _DEFAULT_LAYER_INDEXES = ["https://juju.github.io/layer-index/"]
    LAYER_INDEXES = _DEFAULT_LAYER_INDEXES
    NO_LOCAL_LAYERS = False
    NAMESPACE = "layer"
    ENVIRON = "CHARM_LAYERS_DIR"
    OLD_ENVIRON = "LAYER_PATH"
    OPTIONAL_PREFIX = "juju-layer-"
    ENDPOINT = "layers"
    _DEFAULT_BRANCH = None
    BRANCH = _DEFAULT_BRANCH

    @classmethod
    def set_layer_indexes(cls, layer_indexes):
        if not layer_indexes:
            return
        if isinstance(layer_indexes, str):
            layer_indexes = layer_indexes.split(',')
        new_indexes = []
        for layer_index in layer_indexes:
            if layer_index == 'DEFAULT':
                new_indexes.extend(cls._DEFAULT_LAYER_INDEXES)
            else:
                new_indexes.append(layer_index)
        cls.LAYER_INDEXES = new_indexes

    @classmethod
    def restore_layer_indexes(cls):
        cls.LAYER_INDEXES = cls._DEFAULT_LAYER_INDEXES

    @classmethod
    def set_branch(cls, branch):
        if not branch:
            return
        cls.BRANCH = branch

    @classmethod
    def restore_branch(cls):
        cls.BRANCH = cls._DEFAULT_BRANCH

    @classmethod
    def can_fetch(cls, url):
        # Search local path first, then the interface webservice
        if url.startswith("{}:".format(cls.NAMESPACE)):
            remaining = url[len(cls.NAMESPACE) + 1:]
            parts = remaining.split("@", 2)
            name = parts[0]
            try:
                revision = parts[1]
            except IndexError:
                revision = None

            if not cls.NO_LOCAL_LAYERS:
                prefixed_name = '{}-{}'.format(cls.NAMESPACE, name)
                search_path = []
                if cls.ENVIRON in os.environ:
                    search_path.append(os.environ[cls.ENVIRON])
                elif cls.OLD_ENVIRON in os.environ:
                    search_path.append(os.environ[cls.OLD_ENVIRON])
                else:
                    search_path.append(os.environ.get("JUJU_REPOSITORY", "."))
                for part in search_path:
                    basepath = path(part)
                    for dirname in (name, prefixed_name):
                        p = (basepath / dirname).normpath()
                        if p.exists():
                            return dict(path=p)

            choices = [name]
            if name.startswith(cls.OPTIONAL_PREFIX):
                choices.append(name[len(cls.OPTIONAL_PREFIX):])
            for choice in choices:
                for layer_index in cls.LAYER_INDEXES:
                    uri = "%s%s/%s.json" % (
                        layer_index, cls.ENDPOINT, choice)
                    log.debug('Checking layer index: {}'.format(uri))
                    if uri.startswith('file://'):
                        choice_path = path(uri[7:])
                        if not choice_path.exists():
                            continue
                        try:
                            result = json.loads(choice_path.text())
                        except json.JSONDecodeError as e:
                            log.error('Unable to parse index entry for {}: '
                                      '{}'.format(url, e))
                            continue
                        if not result.get('repo'):
                            continue
                        log.debug('Found repo: {}'.format(result['repo']))
                        if revision:
                            result.update(revision=revision)
                        return result
                    try:
                        result = requests.get(uri)
                    except Exception:
                        result = None
                    if result and result.ok:
                        result = result.json()
                        if result.get("repo"):
                            log.debug('Found repo: {}'.format(result['repo']))
                            if revision:
                                result.update(revision=revision)
                            return result
            return {}

    def target(self, dir_):
        """Return a :class:`path` of the directory where the downloaded item
        will be located.

        :param str dir_: Directory into which the item will be downloaded.
        :return: :class:`path`

        """
        if hasattr(self, "path"):
            return self.path
        elif hasattr(self, "repo"):
            _, target = self._get_repo_fetcher_and_target(self.repo, dir_)
            return target

    def _get_repo_fetcher_and_target(self, repo, dir_):
        """Returns a :class:`Fetcher` for ``repo``, and the destination dir
        at which the downloaded repo will be created.

        :param str repo: The repo url.
        :param str dir_: Directory into which the repo will be downloaded.
        :return: 2-tuple of (:class:`Fetcher`, :class:`path`)

        """
        u = self.url[len(self.NAMESPACE) + 1:]
        if '@' in u:
            u = u.split('@')[0]
        if getattr(self, 'revision', ''):
            f = get_fetcher("{}@{}".format(repo, self.revision))
        else:
            f = get_fetcher(repo)
        return f, path(dir_) / u

    def fetch(self, dir_):
        if hasattr(self, "path"):
            return super(LayerFetcher, self).fetch(dir_)
        elif hasattr(self, "repo"):
            f, target = self._get_repo_fetcher_and_target(self.repo, dir_)
            log.debug('Using fetcher: {}'.format(f))
            if self.BRANCH is not None:
                log.debug('Adding branch: %s', self.BRANCH)
                f.revision = self.BRANCH
            orig_res = res = f.fetch(dir_)
            log.debug("url fetched (for lockfile): %s",
                      getattr(f, 'fetched_url'))
            self.fetched_url = getattr(f, 'fetched_url', None)
            self.vcs = getattr(f, 'vcs', None)
            # make sure we save the revision of the actual repo, before we
            # start traversing subdirectories and moving contents around
            self.revision = self.get_revision(res)
            if res != target:
                res = path(res)
                if hasattr(self, 'subdir'):
                    res = res / self.subdir
                target.rmtree_p()
                log.debug('Copying {} to {}'.format(res, target))
                shutil.copytree(res, target)
                log.debug('Cleaning up {}'.format(orig_res))
                path(orig_res).rmtree_p()  # cleanup from cache after copied
            return target


fetchers.FETCHERS.insert(0, LayerFetcher)


class InterfaceFetcher(LayerFetcher):
    NAMESPACE = "interface"
    ENVIRON = "CHARM_INTERFACES_DIR"
    OLD_ENVIRON = "INTERFACE_PATH"
    OPTIONAL_PREFIX = "juju-relation-"
    ENDPOINT = "interfaces"


fetchers.FETCHERS.insert(0, InterfaceFetcher)
