import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile

import requests
import yaml

from charmworldlib.bundle import Bundle

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECS = 45


def get(*args, **kw):
    if 'timeout' not in kw:
        kw['timeout'] = REQUEST_TIMEOUT_SECS

    return requests.get(*args, **kw)


def rename(dir_):
    """If ``dir_`` is a charm directory, rename it to match the
    charm name, otherwise do nothing.

    :param dir_: directory path
    :return: the new directory name (possibly unchanged).

    """
    dir_ = dir_.rstrip(os.sep)
    metadata = os.path.join(dir_, "metadata.yaml")
    if not os.path.exists(metadata):
        return dir_
    metadata = yaml.safe_load(open(metadata))
    name = metadata.get("name")
    if not name:
        return dir_
    new_dir = os.path.join(os.path.dirname(dir_), name)
    if not os.path.exists(new_dir):
        # This ignores existing repos
        # In truth we want control over management of existing
        # repos with per VCS branch selections
        # ex: switching the git branch marked in revision
        os.rename(dir_, new_dir)
    return new_dir


class Fetcher(object):
    def __init__(self, url, **kw):
        self.revision = ''
        self.url = url
        for k, v in kw.items():
            setattr(self, k, v)

    @classmethod
    def can_fetch(cls, url):
        match = cls.MATCH.search(url)
        return match.groupdict() if match else {}

    def get_revision(self, dir_):
        dirlist = os.listdir(dir_)
        if '.bzr' in dirlist:
            rev_info = check_output('bzr revision-info', cwd=dir_)
            return rev_info.split()[1]
        elif '.git' in dirlist:
            return check_output('git rev-parse HEAD', cwd=dir_)
        elif '.hg' in dirlist:
            return check_output(
                "hg log -l 1 --template '{node}\n' -r .", cwd=dir_)
        else:
            return self.revision


class BzrFetcher(Fetcher):
    MATCH = re.compile(r"""
    ^(lp:|launchpad:|https?://((code|www)\.)?launchpad.net/)
    (?P<repo>[^@]*)(@(?P<revision>.*))?$
    """, re.VERBOSE)

    @classmethod
    def can_fetch(cls, url):
        matchdict = super(BzrFetcher, cls).can_fetch(url)
        return matchdict if '/+merge/' not in matchdict.get('repo', '') else {}

    def fetch(self, dir_):
        dir_ = tempfile.mkdtemp(dir=dir_)
        url = 'lp:' + self.repo
        cmd = 'branch --use-existing-dir {} {}'.format(url, dir_)
        if self.revision:
            cmd = '{} -r {}'.format(cmd, self.revision)
        bzr(cmd)
        return rename(dir_)


class BzrMergeProposalFetcher(BzrFetcher):
    @classmethod
    def can_fetch(cls, url):
        matchdict = super(BzrFetcher, cls).can_fetch(url)
        return matchdict if '/+merge/' in matchdict.get('repo', '') else {}

    def fetch(self, dir_):
        dir_ = tempfile.mkdtemp(dir=dir_)
        api_base = 'https://api.launchpad.net/devel/'
        url = api_base + self.repo
        merge_data = get(url).json()
        target = 'lp:' + merge_data['target_branch_link'][len(api_base):]
        source = 'lp:' + merge_data['source_branch_link'][len(api_base):]
        bzr('branch --use-existing-dir {} {}'.format(target, dir_))
        bzr('merge {}'.format(source), cwd=dir_)
        bzr('commit --unchanged -m "Merge commit"', cwd=dir_)
        return rename(dir_)


class GithubFetcher(Fetcher):
    MATCH = re.compile(r"""
    ^(gh:|github:|https?://(www\.)?github.com/)
    (?P<repo>[^@]*)(@(?P<revision>.*))?$
    """, re.VERBOSE)

    def fetch(self, dir_):
        dir_ = tempfile.mkdtemp(dir=dir_)
        url = 'https://github.com/' + self.repo
        git('clone {} {}'.format(url, dir_))
        if self.revision:
            git('checkout {}'.format(self.revision), cwd=dir_)
        return rename(dir_)


class BitbucketFetcher(Fetcher):
    MATCH = re.compile(r"""
    ^(bb:|bitbucket:|https?://(www\.)?bitbucket.org/)
    (?P<repo>[^@]*)(@(?P<revision>.*))?$
    """, re.VERBOSE)

    def fetch(self, dir_):
        dir_ = tempfile.mkdtemp(dir=dir_)
        url = 'https://bitbucket.org/' + self.repo
        if url.endswith('.git'):
            return self._fetch_git(url, dir_)
        return self._fetch_hg(url, dir_)

    def _fetch_git(self, url, dir_):
        git('clone {} {}'.format(url, dir_))
        if self.revision:
            git('checkout {}'.format(self.revision), cwd=dir_)
        return rename(dir_)

    def _fetch_hg(self, url, dir_):
        cmd = 'clone {} {}'.format(url, dir_)
        if self.revision:
            cmd = '{} -u {}'.format(cmd, self.revision)
        hg(cmd)
        return rename(dir_)


class LocalFetcher(Fetcher):
    @classmethod
    def can_fetch(cls, url):
        src = os.path.abspath(
            os.path.join(os.getcwd(), os.path.expanduser(url)))
        if os.path.exists(src):
            return dict(path=src)
        return {}

    def fetch(self, dir_):
        dst = os.path.join(dir_, os.path.basename(self.path.rstrip(os.sep)))
        shutil.copytree(self.path, dst, symlinks=True)
        return dst


class StoreCharm(object):
    STORE_URL = 'https://store.juju.ubuntu.com/charm-info'

    def __init__(self, name):
        self.name = name
        self.data = self.fetch()

    def __getattr__(self, key):
        return self.data[key]

    def fetch(self):
        params = {
            'stats': 0,
            'charms': self.name,
        }
        r = get(self.STORE_URL, params=params).json()
        charm_data = r[self.name]
        if 'errors' in charm_data:
            raise FetchError(
                'Error retrieving "{}" from charm store: {}'.format(
                    self.name, '; '.join(charm_data['errors']))
            )
        return charm_data


class CharmstoreDownloader(Fetcher):
    MATCH = re.compile(r"""
    ^cs:(?P<charm>.*)$
    """, re.VERBOSE)

    STORE_URL = 'https://store.juju.ubuntu.com/charm/'

    def __init__(self, *args, **kw):
        super(CharmstoreDownloader, self).__init__(*args, **kw)
        self.charm = StoreCharm(self.charm)

    def fetch(self, dir_):
        url = self.charm.data['canonical-url'][len('cs:'):]
        url = self.STORE_URL + url
        archive = self.download_file(url, dir_)
        charm_dir = self.extract_archive(archive, dir_)
        return rename(charm_dir)

    def extract_archive(self, archive, dir_):
        tempdir = tempfile.mkdtemp(dir=dir_)
        log.debug("Extracting %s to %s", archive, tempdir)
        # Can't  extract with python due to bug that drops file
        # permissions: http://bugs.python.org/issue15795
        # In particular, it's important that executable test files in the
        # archive remain executable, otherwise the tests won't be run.
        # Instead we use a shell equivalent of the following:
        #     archive = zipfile.ZipFile(archive, 'r')
        #     archive.extractall(tempdir)
        check_call('unzip {} -d {}'.format(archive, tempdir))
        return tempdir

    def download_file(self, url, dir_):
        _, filename = tempfile.mkstemp(dir=dir_)
        log.debug("Downloading %s", url)
        r = get(url, stream=True)
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        return filename

    def get_revision(self, dir_):
        return self.charm.revision


class BundleDownloader(Fetcher):
    MATCH = re.compile(r"""
    ^bundle:(?P<bundle>.*)$
    """, re.VERBOSE)

    def fetch(self, dir_):
        url = Bundle(self.bundle).deployer_file_url
        bundle_dir = self.download_file(url, dir_)
        return bundle_dir

    def download_file(self, url, dir_):
        bundle_dir = tempfile.mkdtemp(dir=dir_)
        bundle_file = os.path.join(bundle_dir, 'bundles.yaml')
        log.debug("Downloading %s to %s", url, bundle_file)
        r = get(url, stream=True)
        with open(bundle_file, 'w') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        return bundle_dir

    def get_revision(self, dir_):
        return Bundle(self.bundle).basket_revision


def bzr(cmd, **kw):
    check_call('bzr ' + cmd, **kw)


def git(cmd, **kw):
    check_call('git ' + cmd, **kw)


def hg(cmd, **kw):
    check_call('hg ' + cmd, **kw)


def check_call(cmd, **kw):
    return check_output(cmd, **kw)


class FetchError(Exception):
    pass


def check_output(cmd, **kw):
    args = shlex.split(cmd)
    p = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kw
    )
    out, _ = p.communicate()
    if p.returncode != 0:
        raise FetchError(out)
    log.debug('%s: %s', cmd, out)
    return out


FETCHERS = [
    BzrFetcher,
    BzrMergeProposalFetcher,
    GithubFetcher,
    BitbucketFetcher,
    LocalFetcher,
    CharmstoreDownloader,
    BundleDownloader,
]


def get_fetcher(url):
    for fetcher in FETCHERS:
        matchdict = fetcher.can_fetch(url)
        if matchdict:
            return fetcher(url, **matchdict)
    raise FetchError('No fetcher for url: %s' % url)
