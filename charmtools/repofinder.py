import re
import subprocess

from collections import namedtuple
import six

from . import utils

try:
    from subprocess import DEVNULL
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


def get_recommended_repo(path):
    """Given vcs directory ``path``, returns the url from which the repo
    can be cloned.

    For git, an 'upstream' remote will be preferred over 'origin'.
    For bzr, the :parent: branch will be preferred.
    For hg, the 'default' alias will be preferred.

    Returns None if the directory is not a repo, or a remote url can not
    be determined.

    :param path: A :class:`path.path` to a directory
    :return: A url string, or None

    """

    Command = namedtuple("Command", "args parse")
    cmds = [
        Command(['git', 'remote', '-v'], _parse_git),
        Command(['bzr', 'info'], _parse_bzr),
        Command(['hg', 'paths'], _parse_hg),
    ]

    if not path.exists():
        return None

    with utils.cd(str(path)):
        for cmd in cmds:
            try:
                output = subprocess.check_output(cmd.args, stderr=DEVNULL)
                if six.PY3:
                    output = str(output)
                if output:
                    repo = cmd.parse(output)
                    if repo:
                        return repo
            except (subprocess.CalledProcessError, OSError):
                continue


def _parse_git(txt):
    pat = re.compile(
        r'(?P<name>\S+)\s+(?P<url>\S+)\s+\((?P<type>[^\)]+)\)')
    urls = {}
    for line in txt.split('\n'):
        match = pat.search(line)
        if match:
            d = match.groupdict()
            if d['name'] == 'upstream' and d['type'] == 'fetch':
                return d['url'].strip()
            elif d['type'] == 'fetch':
                urls[d['name']] = d['url'].strip()

    if 'origin' in urls:
        return urls['origin']

    for url in urls.values():
        return url


def _parse_bzr(txt):
    branch_types = ['parent', 'push', 'submit']
    pat = re.compile(
        r'(?P<branch_type>({})) branch: (?P<url>.*)'.format(
            '|'.join(branch_types)))
    matches = {}
    for line in txt.split('\n'):
        match = pat.search(line)
        if match:
            d = match.groupdict()
            matches[d['branch_type']] = d['url'].strip()
    if not matches:
        return
    for typ in branch_types:
        url = matches.get(typ)
        if url:
            return url


def _parse_hg(txt):
    pat = re.compile(r'(?P<name>[^\s]+) = (?P<url>.*)')
    urls = []
    for line in txt.split('\n'):
        match = pat.search(line)
        if match:
            d = match.groupdict()
            if d['name'] == 'default':
                return d['url'].strip()
            else:
                urls.append(d['url'].strip())
    return urls[0] if urls else None
