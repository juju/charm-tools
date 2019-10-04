import os
import shutil
import tempfile
import unittest

from charmtools.fetchers import (
    BzrFetcher,
    BzrMergeProposalFetcher,
    GithubFetcher,
    OpendevFetcher,
    GitFetcher,
    BitbucketFetcher,
    LocalFetcher,
    CharmstoreDownloader,
    BundleDownloader,
    rename,
    normalize_bundle_name,
)


class RenameTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.directory):
            shutil.rmtree(self.directory)

    def test_rename_no_meta(self):
        self.assertEqual(rename(self.directory), self.directory)

    def test_rename_no_name(self):
        path = os.path.join(self.directory, "metadata.yaml")
        with open(path, "w") as fp:
            fp.write("another: key\n")
        self.assertEqual(rename(self.directory), self.directory)

    def test_rename_with_name(self):
        d = tempfile.mkdtemp(dir=self.directory)
        path = os.path.join(d, "metadata.yaml")
        with open(path, "w") as fp:
            fp.write("name: foo\n")
        self.assertEqual(os.path.basename(rename(d)), "foo")


class BzrFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = BzrFetcher.can_fetch

        good_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('launchpad:~tvansteenburgh/charms/precise/foo'),
            f('http://launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('https://launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('http://www.launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('https://www.launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('http://code.launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('https://code.launchpad.net/~tvansteenburgh/charms/precise/foo'),
            f('bzr+ssh://bazaar.launchpad.net/~tvansteenburgh/charms/precise/foo'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('gh:charms/meteor'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(
                test['repo'],
                '~tvansteenburgh/charms/precise/foo')

        for test in bad_tests:
            self.assertEqual(test, {})


class BzrMergeProposalFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = BzrMergeProposalFetcher.can_fetch

        good_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('gh:charms/meteor'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(
                test['repo'],
                '~tvansteenburgh/charms/precise/foo/+merge/12345')

        for test in bad_tests:
            self.assertEqual(test, {})


class GithubFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = GithubFetcher.can_fetch

        good_tests = [
            f('gh:charms/meteor'),
            f('github:charms/meteor'),
            f('http://github.com/charms/meteor'),
            f('https://github.com/charms/meteor'),
            f('http://www.github.com/charms/meteor'),
            f('https://www.github.com/charms/meteor'),
            f('git@github.com:charms/meteor'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(test['repo'], 'charms/meteor')

        for test in bad_tests:
            self.assertEqual(test, {})


class OpendevFetcherGenericTest(unittest.TestCase):
    def test_can_fetch(self):
        f = OpendevFetcher.can_fetch

        good_tests = [
            f('https://opendev.org/charms/foo'),
            f('https://www.opendev.org/charms/foo'),
            f('git@opendev.org:charms/foo'),
        ]

        bad_tests = [
            f('http://www.opendev.org/charms/foo'),
            f('http://opendev.org/charms/foo'),
            f('https://opendev.com/charms/foo'),
            f('https://www.opendev.com/charms/foo'),
            f('git@opendev.com:charms/foo'),
            f('gh:charms/foo'),
            f('github:charms/foo'),
            f('http://github.com/charms/foo'),
            f('https://github.com/charms/foo'),
            f('http://www.github.com/charms/foo'),
            f('https://www.github.com/charms/foo'),
            f('git@github.com:charms/foo'),
            f('lp:~openstack-charmers/charms/bionic/foo'),
            f('lp:~openstack-charmers/charms/bionic/foo/+merge/12345'),
            f('bb:charms/foo'),
            f('local:~/src/charms/bionic/foo'),
            f('cs:bionic/foo'),
            f('bundle:openstack-base/single'),
        ]

        for test in good_tests:
            self.assertEqual(test['repo'], 'charms/foo')

        for test in bad_tests:
            self.assertEqual(test, {})


class OpendevFetcherSpecificTest(unittest.TestCase):
    def test_can_fetch(self):
        f = OpendevFetcher.can_fetch

        good_tests = [
            f('https://opendev.org/x/charm-interface-barbican-hsm'),
            f('https://www.opendev.org/x/charm-interface-barbican-hsm'),
            f('git@opendev.org:x/charm-interface-barbican-hsm'),
        ]

        bad_tests = [
            f('http://opendev.org/x/charm-interface-barbican-hsm'),
            f('http://www.opendev.org/x/charm-interface-barbican-hsm'),
            f('https://opendev.com/x/charm-interface-barbican-hsm'),
            f('https://www.opendev.com/x/charm-interface-barbican-hsm'),
            f('git@opendev.com:x/charm-interface-barbican-hsm'),
            f('gh:x/charm-interface-barbican-hsm'),
            f('github:x/charm-interface-barbican-hsm'),
            f('http://github.com/x/charm-interface-barbican-hsm'),
            f('https://github.com/x/charm-interface-barbican-hsm'),
            f('http://www.github.com/x/charm-interface-barbican-hsm'),
            f('https://www.github.com/x/charm-interface-barbican-hsm'),
            f('git@github.com:x/charm-interface-barbican-hsm'),
            f('lp:~openstack-charmers/x/charm-interface-barbican-hsm'),
            f('lp:~openstack-charmers/x/charm-interface-barbican-hsm/+merge/12345'),
            f('bb:x/charm-interface-barbican-hsm'),
            f('local:~/src/charms/bionic/x/charm-interface-barbican-hsm'),
            f('cs:bionic/x/charm-interface-barbican-hsm'),
            f('bundle:openstack-base/x/charm-interface-barbican-hsm'),
        ]

        for test in good_tests:
            self.assertEqual(test['repo'], 'x/charm-interface-barbican-hsm')

        for test in bad_tests:
            self.assertEqual(test, {})


class GitFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = GitFetcher.can_fetch

        good_tests = [
            'git@foobar.com:charms/meteor',
            'https://foobar.com/meteor.git',
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(f(test)['repo'], test)

        for test in bad_tests:
            self.assertEqual(test, {})


class BitbucketFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = BitbucketFetcher.can_fetch

        good_tests = [
            f('bb:charms/meteor'),
            f('bitbucket:charms/meteor'),
            f('http://bitbucket.org/charms/meteor'),
            f('https://bitbucket.org/charms/meteor'),
            f('http://www.bitbucket.org/charms/meteor'),
            f('https://www.bitbucket.org/charms/meteor'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('gh:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(test['repo'], 'charms/meteor')

        for test in bad_tests:
            self.assertEqual(test, {})


class LocalFetcherTest(unittest.TestCase):
    def test_can_fetch(self):
        f = LocalFetcher.can_fetch

        good_tests = [
            f('/tmp'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('gh:charms/meteor'),
            f('bb:charms/meteor'),
            f('cs:precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(test['path'], '/tmp')

        for test in bad_tests:
            self.assertEqual(test, {})


class CharmstoreDownloaderTest(unittest.TestCase):
    def test_can_fetch(self):
        f = CharmstoreDownloader.can_fetch

        good_tests = [
            f('cs:precise/meteor'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('gh:charms/meteor'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('bundle:mediawiki/single'),
        ]

        for test in good_tests:
            self.assertEqual(test['entity'], 'precise/meteor')

        for test in bad_tests:
            self.assertEqual(test, {})


class BundleDownloaderTest(unittest.TestCase):
    def test_can_fetch(self):
        f = BundleDownloader.can_fetch

        good_tests = [
            f('bundle:mediawiki/single'),
        ]

        bad_tests = [
            f('lp:~tvansteenburgh/charms/precise/foo'),
            f('lp:~tvansteenburgh/charms/precise/foo/+merge/12345'),
            f('gh:charms/meteor'),
            f('bb:charms/meteor'),
            f('local:~/src/charms/precise/meteor'),
            f('cs:precise/meteor'),
        ]

        for test in good_tests:
            self.assertEqual(test['entity'], 'mediawiki/single')

        for test in bad_tests:
            self.assertEqual(test, {})

    def test_normalize_bundle_name(self):
        f = normalize_bundle_name

        inputs = [
            '~charmers/mediawiki/6/single',
            '~charmers/mediawiki/single',
            'mediawiki/single',
            'mediawiki/6/single',
            'mediawiki-single',
            'mediawiki-single-6',
            '~charmers/mediawiki-single-6',
            '~charmers/mediawiki-single',
        ]

        outputs = [
            '~charmers/mediawiki-single-6',
            '~charmers/mediawiki-single',
            'mediawiki-single',
            'mediawiki-single-6',
            'mediawiki-single',
            'mediawiki-single-6',
            '~charmers/mediawiki-single-6',
            '~charmers/mediawiki-single',
        ]

        for i, bundle_name in enumerate(inputs):
            self.assertEqual(f(bundle_name), outputs[i])
