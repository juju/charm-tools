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

from .prompt import Prompt


class CharmTemplate(object):
    """Base plugin for creating a new charm."""

    @property
    def prompts(self):
        """Return a list :class:`Prompt` objects that will be used for
        configuring the charm created by this plugin.

        """
        return []

    def create_charm(self, config, output_path):
        """Create charm files

        :param config: dict of config values gathered interactively from the
            user, loaded from a config file, or as a result of accepting all
            configuration defaults.

        :param output_path: directory into which all charm files and dirs
            should be written.

        """
        raise NotImplementedError

    def configure_prompt(self, prompt, config):
        """Reconfigure a prompt based on already-gathered config options

        Called right before ``prompt`` is rendered to the user or before
        the default value for the prompt is accepted. This gives the plugin
        a chance to reconfigure a prompt in any way necessary based on the
        results of prior prompts (contained in ``config``), including
        changing its :attr:`text` or :attr:`default`.

        Valid return values are the original prompt (modified or not), an
        entirely new :class:`Prompt` object, or None if this prompt should
        be skipped altogether.

        :param config: dict of all configuration values that have been set
            prior to this prompt being called.

        """
        return prompt

    def validate_input(self, input_value, prompt, config):
        """Return the (possibly modified) validated input value, or raise
        ValueError with a message explaining why the value is invalid.

        :param input_value: str entered by user
        :param prompt: :class:`Prompt` object that elicited this input
        :param config: dict of all configuration values that have been set
            prior to this prompt being called.

        """
        return prompt.validate(input_value)


class PythonCharmTemplate(CharmTemplate):
    """Python charm template plugin."""

    @property
    def prompts(self):
        return [
            Prompt('helpers', 'Include charmhelpers? [Y/n]: ', 'y')
        ]

    def create_charm(self, config, output_path):
        # Create all the charm files
        pass
