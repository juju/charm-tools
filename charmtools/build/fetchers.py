import os
import json
import logging

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


class InterfaceFetcher(fetchers.LocalFetcher):
    INTERFACE_DOMAIN = "https://juju.github.io/layer-index/"
    NAMESPACE = "interface"
    ENVIRON = "INTERFACE_PATH"
    OPTIONAL_PREFIX = "juju-relation-"
    ENDPOINT = "interfaces"
    NO_LOCAL_LAYERS = False

    @classmethod
    def can_fetch(cls, url):
        # Search local path first, then the interface webservice
        if url.startswith("{}:".format(cls.NAMESPACE)):
            name = url[len(cls.NAMESPACE) + 1:]

            if not cls.NO_LOCAL_LAYERS:
                prefixed_name = '{}-{}'.format(cls.NAMESPACE, name)
                search_path = [os.environ.get("JUJU_REPOSITORY", ".")]
                cp = os.environ.get(cls.ENVIRON)
                if cp:
                    search_path.extend(cp.split(os.pathsep))
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
                uri = "%s%s/%s.json" % (
                    cls.INTERFACE_DOMAIN, cls.ENDPOINT, choice)
                log.debug('Checking layer index: {}'.format(uri))
                if uri.startswith('file://'):
                    choice_path = path(uri[7:])
                    if not choice_path.exists():
                        continue
                    result = json.loads(choice_path.text())
                    if not result.get('repo'):
                        continue
                    log.debug('Found repo: {}'.format(result['repo']))
                    return result
                try:
                    result = requests.get(uri)
                except Exception:
                    result = None
                if result and result.ok:
                    result = result.json()
                    if result.get("repo"):
                        log.debug('Found repo: {}'.format(result['repo']))
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
        f = get_fetcher(repo)
        return f, path(dir_) / u

    def fetch(self, dir_):
        if hasattr(self, "path"):
            return super(InterfaceFetcher, self).fetch(dir_)
        elif hasattr(self, "repo"):
            f, target = self._get_repo_fetcher_and_target(self.repo, dir_)
            res = f.fetch(dir_)
            if res != target:
                res = path(res)
                if hasattr(self, 'subdir'):
                    res = res / self.subdir
                target.rmtree_p()
                # call this way instead of `res.rename(target)`
                # to make unit test easier
                path.rename(res, target)
            return target


fetchers.FETCHERS.insert(0, InterfaceFetcher)


class LayerFetcher(InterfaceFetcher):
    INTERFACE_DOMAIN = "https://juju.github.io/layer-index/"
    NAMESPACE = "layer"
    ENVIRON = "LAYER_PATH"
    OPTIONAL_PREFIX = "juju-layer-"
    ENDPOINT = "layers"


fetchers.FETCHERS.insert(0, LayerFetcher)
