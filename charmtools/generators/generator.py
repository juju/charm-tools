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

"""
generator = CharmGenerator(cmdline_opts)
generator.create_charm()

"""

import shutil

import yaml


class CharmGenerator(object):
    """Generate a new Charm on the filesystem"""

    def __init__(self, cmdline_opts):
        self.opts = cmdline_opts
        self.plugin = self._load_plugin()

    def _load_plugin(self, template_name):
        """Instantiate and return the plugin defined by the ``template_name``
        entry point.

        """
        # instantiate plugin via pkg_resources.load_entry_point()
        # using self.opts.template
        pass

    def create_charm(self):
        """Gather user configuration and hand it off to the template plugin to
        create the files and directories for the new charm.

        """
        user_config = self._get_user_config()
        output_path = self._get_output_path()
        tempdir = self._get_tempdir()
        try:
            self.plugin.create_charm(user_config, tempdir)
            shutil.copytree(tempdir, output_path)
        finally:
            self._cleanup()

    def _get_user_config(self):
        """Get user configuration by prompting for it interactively, loading
        it from a config file, or using predefined defaults.

        """
        if self.opts.config:
            with open(self.opts.config, 'r') as f:
                config = yaml.safe_load(f.read())
                return self._validate_config(config)
        else:
            config = {}
            for prompt in self.plugin.prompts:
                config[prompt.name] = self._prompt(prompt, config.copy())
            return config

    def _validate_config(self, config):
        """Validate user configuration loaded from a yaml file.

        """
        errors = []
        validated_config = {}
        for prompt in self.plugin.prompts:
            try:
                validated_config[prompt.name] = \
                    self._validate_config_item(
                        config, prompt, validated_config.copy())
            except ValueError as e:
                errors.append(e)
        if errors:
            raise ValueError(
                'Invalid configuration file: {}\n{}'.format(
                    self.opts.config, '\n'.join(errors)))
        return validated_config

    def _validate_config_item(self, user_config, prompt, validated_config):
        """Validate an individual user config option.

        """
        prompt = self.plugin.configure_prompt(prompt, validated_config)
        if not prompt:
            return None
        user_value = user_config.get(prompt.name, '').strip()
        if not user_value:
            return prompt.default
        return self.plugin.validate_input(user_value, prompt, validated_config)

    def _prompt(self, prompt, config):
        """Prompt for and return user input, retrying until valid input
        received.

        If the 'accept_defaults' options is enabled, return the default value
        for the prompt rather than prompting the user.

        """
        prompt = self.plugin.configure_prompt(prompt, config)
        if not prompt:
            return None
        if self.opts.accept_defaults:
            return prompt.default
        user_input = raw_input(prompt.text).strip()
        if not user_input:
            return prompt.default
        try:
            return self.plugin.validate_input(user_input, prompt, config)
        except ValueError as e:
            print(str(e))
            return self._prompt(prompt, config)
