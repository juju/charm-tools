"""Unit test for juju_test"""

import os
import unittest
import yaml

from charmtools.get import parse_charm_id, download, setup_parser, main
from mock import patch, call, Mock, MagicMock

from cStringIO import StringIO


class Charm(object):
    def __init__(self):
        self.name = 'dummy'
        self.code_source = {'location': 'lp:tmp'}


class JujuCharmGetTest(unittest.TestCase):
    @patch('charmworldlib.charm.Charm')
    def test_parse_charm_id(self, mCharm):
        self.assertEqual(mCharm(), parse_charm_id('precise/dummy-0'))
        mCharm.assert_called_with('precise/dummy-0')

    @patch('charmworldlib.charm.Charm')
    def test_parse_charm_id_cs(self, mCharm):
        self.assertEqual(mCharm(), parse_charm_id('cs:precise/dummy-0'))
        mCharm.assert_called_with('precise/dummy-0')

    @patch('charmworldlib.charm.Charm')
    def test_parse_charm_id_notfound(self, mCharm):
        mCharm.side_effect = Exception('Charm not found')
        self.assertEqual(None, parse_charm_id('precise/dummy-0'))

    @patch('charmtools.get.Mr')
    @patch('os.path.exists')
    def test_download(self, mock_exists, mMr):
        c = Charm()
        mock_exists.side_effect = [False, True]
        download(c, '/tmp')
        mMr.assert_called_with('/tmp', mr_compat=False)

    @patch('os.listdir')
    @patch('os.path.exists')
    def test_download_dir_exists(self, mock_exists, mock_listdir):
        c = Charm()
        mock_exists.side_effect = [True]
        mock_listdir.side_effect = [True]
        self.assertRaises(ValueError, download, c, '/tmp')

    @patch('charmtools.get.Mr')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_download_create_dir(self, mock_makedirs, mock_exists, mMr):
        c = Charm()
        mock_exists.side_effect = [False, False]
        download(c, '/tmp')
        mock_makedirs.assert_called_with('/tmp')

    @patch('charmtools.get.parse_charm_id')
    @patch('charmtools.get.download')
    @patch('sys.stderr')
    def test_main(self, mock_stderr, mdownload, mpci):
        c = Charm()
        mock_stderr.side_effect = MagicMock
        mpci.side_effect = [c]
        main(['precise/dummy-0', '/tmp'])
        mdownload.assert_called_with(c, '/tmp')
        mpci.assert_called_with('precise/dummy-0')

    @patch('charmtools.get.parse_charm_id')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_main_bad_charm(self, mock_exit, mock_stderr, mpci):
        mock_stderr.side_effect = MagicMock
        mpci.side_effect = [None]
        mock_exit.side_effect = SystemExit
        self.assertRaises(SystemExit, main, ['precise/badcharm-0', '/tmp'])
        mpci.assert_called_with('precise/badcharm-0')
        mock_exit.assert_called_with(1)

    @patch('charmtools.get.parse_charm_id')
    @patch('charmtools.get.download')
    @patch('sys.stderr')
    @patch('sys.exit')
    def test_main_bad_download(self, mock_exit, mock_stderr, mdownload, mpci):
        c = Charm()
        mock_stderr.side_effect = MagicMock
        mpci.side_effect = [c]
        mock_exit.side_effect = SystemExit
        mdownload.side_effect = Exception
        self.assertRaises(SystemExit, main, ['precise/faildownload-0', '/tmp'])
        mpci.assert_called_with('precise/faildownload-0')
        mock_exit.assert_called_with(1)

    def test_setup_parser(self):
        import argparse

        self.assertTrue(isinstance(setup_parser(), argparse.ArgumentParser))
