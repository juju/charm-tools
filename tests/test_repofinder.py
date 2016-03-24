import textwrap
import unittest
from charmtools import repofinder


class TestRepoFinder(unittest.TestCase):

    def test__parse_git(self):
        s = textwrap.dedent("""\
        origin  git@github.com:tvansteenburgh/charm-tools.git (fetch)
        origin  git@github.com:tvansteenburgh/charm-tools.git (push)
        upstream        git@github.com:juju/charm-tools-fetch.git (fetch)
        upstream        git@github.com:juju/charm-tools.git (push)
        """)
        self.assertEqual(
            repofinder._parse_git(s),
            'git@github.com:juju/charm-tools-fetch.git'
        )

    def test__parse_hg(self):
        s = textwrap.dedent("""\
        default = https://tvansteenburgh@bitbucket.org/tvansteenburgh/loopy
        """)
        self.assertEqual(
            repofinder._parse_hg(s),
            'https://tvansteenburgh@bitbucket.org/tvansteenburgh/loopy'
        )

    def test__parse_bzr_parent(self):
        s = textwrap.dedent("""\
        Standalone tree (format: 2a)
        Location:
          branch root: .

        Related branches:
            push branch: bzr+ssh://bazaar.launchpad.net/~tvansteenburgh/juju-deployer/1269783-force-terminate/
          parent branch: bzr+ssh://bazaar.launchpad.net/+branch/juju-deployer/
          submit branch: bzr+ssh://bazaar.launchpad.net/~bac/juju-deployer/update-store-url/
        """)
        self.assertEqual(
            repofinder._parse_bzr(s),
            'bzr+ssh://bazaar.launchpad.net/+branch/juju-deployer/'
        )

    def test__parse_bzr_push(self):
        s = textwrap.dedent("""\
        Standalone tree (format: 2a)
        Location:
          branch root: .

        Related branches:
            push branch: bzr+ssh://bazaar.launchpad.net/~tvansteenburgh/juju-deployer/1269783-force-terminate/
          submit branch: bzr+ssh://bazaar.launchpad.net/~bac/juju-deployer/update-store-url/
        """)
        self.assertEqual(
            repofinder._parse_bzr(s),
            'bzr+ssh://bazaar.launchpad.net/~tvansteenburgh/juju-deployer/1269783-force-terminate/'
        )

    def test__parse_bzr_submit(self):
        s = textwrap.dedent("""\
        Standalone tree (format: 2a)
        Location:
          branch root: .

        Related branches:
          submit branch: bzr+ssh://bazaar.launchpad.net/~bac/juju-deployer/update-store-url/
        """)
        self.assertEqual(
            repofinder._parse_bzr(s),
            'bzr+ssh://bazaar.launchpad.net/~bac/juju-deployer/update-store-url/'
        )
