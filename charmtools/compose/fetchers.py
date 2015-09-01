import re
import tempfile
import os

import requests
from charmtools import fetchers
from charmtools.fetchers import (git,  # noqa
                                 Fetcher,
                                 get_fetcher,
                                 FetchError)

from path import path


class RepoFetcher(fetchers.LocalFetcher):
    @classmethod
    def can_fetch(cls, url):
        search_path = [os.getcwd(), os.environ.get("JUJU_REPOSITORY", ".")]
        cp = os.environ.get("COMPOSER_PATH")
        if cp:
            search_path.extend(cp.split(":"))
        for part in search_path:
            p = (path(part) / url).normpath()
            if p.exists():
                return dict(path=p)
        return {}

fetchers.FETCHERS.insert(0, RepoFetcher)


class InterfaceFetcher(fetchers.LocalFetcher):
    # XXX: When hosted somewhere, fix this
    INTERFACE_DOMAIN = "http://interfaces.juju.solutions"
    NAMESPACE = "interface"
    ENVIRON = "INTERFACE_PATH"
    OPTIONAL_PREFIX = "juju-relation-"
    ENDPOINT = "/api/v1/interface"

    @classmethod
    def can_fetch(cls, url):
        # Search local path first, then
        # the interface webservice
        if url.startswith("{}:".format(cls.NAMESPACE)):
            url = url[len(cls.NAMESPACE) + 1:]
            search_path = [os.environ.get("JUJU_REPOSITORY", ".")]
            cp = os.environ.get(cls.ENVIRON)
            if cp:
                search_path.extend(cp.split(os.pathsep))
            for part in search_path:
                p = (path(part) / url).normpath()
                if p.exists():
                    return dict(path=p)

            choices = [url]
            if url.startswith(cls.OPTIONAL_PREFIX):
                choices.append(url[len(cls.OPTIONAL_PREFIX):])
            for choice in choices:
                uri = "%s%s/%s/" % (
                    cls.INTERFACE_DOMAIN, cls.ENDPOINT, choice)
                try:
                    result = requests.get(uri)
                except:
                    result = None
                if result and result.ok:
                    result = result.json()
                    if "repo" in result:
                        return result
            return {}

    def fetch(self, dir_):
        if hasattr(self, "path"):
            return super(InterfaceFetcher, self).fetch(dir_)
        elif hasattr(self, "repo"):
            # use the github fetcher for now
            u = self.url[10:]
            f = get_fetcher(self.repo)
            if hasattr(f, "repo"):
                basename = path(f.repo).name.splitext()[0]
            else:
                basename = u
            res = f.fetch(dir_)
            target = dir_ / basename
            if res != target:
                target.rmtree_p()
                path(res).rename(target)
            return target


fetchers.FETCHERS.insert(0, InterfaceFetcher)


class LayerFetcher(InterfaceFetcher):
    INTERFACE_DOMAIN = "http://interfaces.juju.solutions"
    NAMESPACE = "layer"
    ENVIRON = "COMPOSER_PATH"
    OPTIONAL_PREFIX = "juju-layer-"
    ENDPOINT = "/api/v1/layer"

fetchers.FETCHERS.insert(0, LayerFetcher)


class LaunchpadGitFetcher(Fetcher):
    # XXX: this should be upstreamed
    MATCH = re.compile(r"""
    ^(git:|https)?://git.launchpad.net/
    (?P<repo>[^@]*)(@(?P<revision>.*))?$
    """, re.VERBOSE)

    def fetch(self, dir_):
        dir_ = tempfile.mkdtemp(dir=dir_)
        url = 'https://git.launchpad.net/' + self.repo
        git('clone {} {}'.format(url, dir_))
        if self.revision:
            git('checkout {}'.format(self.revision), cwd=dir_)
        return dir_

fetchers.FETCHERS.append(LaunchpadGitFetcher)
