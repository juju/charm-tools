#!/usr/bin/python

#    Copyright (C) 2014  Canonical Ltd.
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
from __future__ import absolute_import

import os
import six
import shutil
import tempfile
from mock import patch, Mock
from unittest import TestCase

from charmtools.generators import (
    CharmGenerator,
    CharmGeneratorException,
    Prompt,
)

from charmtools.templates.bash import BashCharmTemplate


class CharmGeneratorTest(TestCase):
    def setUp(self):
        class opts(object):
            charmname = 'testcharm'
            charmhome = tempfile.mkdtemp()
            template = 'bash'
            accept_defaults = False

        self.c = CharmGenerator(opts)

    def tearDown(self):
        shutil.rmtree(self.c.opts.charmhome, ignore_errors=True)

    def test_load_plugin(self):
        plugin = self.c._load_plugin()

        self.assertIsInstance(plugin, BashCharmTemplate)

    @patch.dict(os.environ, {'USER': 'test'})
    @patch('os.path.expanduser')
    def test_create_charm_output_path_exists(self, eu):
        eu.return_value = self.c.opts.charmhome
        os.mkdir(self.c._get_output_path())
        with self.assertRaises(CharmGeneratorException) as e:
            self.c.create_charm()
            self.assertEqual(
                str(e),
                '{} exists. Please move it out of the way.'.format(
                    self.c._get_output_path()))

    def test_create_charm_error(self):
        with patch.object(self.c.plugin, 'create_charm') as create_charm, \
                patch.object(self.c, '_cleanup') as _cleanup:
            create_charm.side_effect = Exception
            with self.assertRaises(Exception):
                self.c.create_charm()
                self.assertTrue(_cleanup.called)

    @patch('charmtools.generators.generator.apt_fill')
    @patch('charmtools.generators.generator.get_maintainer')
    def test_get_metadata(self, get_maintainer, apt_fill):
        get_maintainer.return_value = ('Tester', 'tester@example.com')
        apt_fill.return_value = {
            'summary': 'Charm summary',
            'description': 'Charm description',
        }
        self.assertEqual(
            self.c._get_metadata(), {
                'package': 'testcharm',
                'maintainer': 'Tester <tester@example.com>',
                'summary': 'Charm summary',
                'description': 'Charm description'})

    @patch('charmtools.generators.generator.rinput')
    def test_get_user_config_from_prompts(self, raw_input_):
        raw_input_.return_value = 'Yes'
        with patch.object(self.c.plugin, 'prompts') as prompts:
            prompts.return_value = [
                Prompt('symlink', 'symlink hooks?', 'y', 'bool')]
            config = self.c._get_user_config()

            self.assertEqual(config, {'symlink': True})

    def test_get_user_config_from_defaults(self):
        self.c.opts.accept_defaults = True
        with patch.object(self.c.plugin, 'prompts') as prompts:
            prompts.return_value = [
                Prompt('symlink', 'symlink hooks?', 'y', 'bool')]
            config = self.c._get_user_config()

            self.assertEqual(config, {'symlink': True})

    def test_prompt_none(self):
        with patch.object(self.c.plugin, 'configure_prompt') as f:
            f.return_value = None

            self.assertIsNone(self.c._prompt(Mock(), {}))

    def test_prompt_accept_default(self):
        self.c.opts.accept_defaults = True
        prompt = Prompt('symlink', 'symlink hooks?', 'y', 'bool')

        self.assertTrue(self.c._prompt(prompt, {}))

    @patch('charmtools.generators.generator.rinput')
    def test_prompt_no_input(self, raw_input_):
        raw_input_.return_value = ''
        prompt = Prompt('symlink', 'symlink hooks?', 'y', 'bool')

        self.assertTrue(self.c._prompt(prompt, {}))

    @patch('charmtools.generators.generator.rinput')
    def test_prompt_invalid_input(self, raw_input_):
        raw_input_.side_effect = ['foo', '18']
        prompt = Prompt('age', 'your age?', '42', 'int')

        self.assertEqual(self.c._prompt(prompt, {}), 18)
        self.assertEqual(raw_input_.call_count, 2)

    @patch('charmtools.generators.generator.rinput')
    def test_prompt_valid_input(self, raw_input_):
        raw_input_.return_value = 'Joe'
        prompt = Prompt('name', 'your name?', 'Name')

        self.assertEqual(self.c._prompt(prompt, {}), 'Joe')
        self.assertEqual(raw_input_.call_count, 1)

    def test_get_output_path(self):
        path = self.c._get_output_path()
        self.assertEqual(
            path,
            os.path.join(self.c.opts.charmhome, self.c.opts.charmname))

    def test_get_tempdir(self):
        tempdir = self.c._get_tempdir()
        self.assertTrue(os.path.isdir(tempdir))
        self.c._cleanup(tempdir)

    def test_cleanup(self):
        tempdir = self.c._get_tempdir()
        self.c._cleanup(tempdir)
        self.assertFalse(os.path.exists(tempdir))
