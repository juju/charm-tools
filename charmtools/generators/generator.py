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

import logging
import os
import shutil
import tempfile

import pkg_resources

from .utils import apt_fill

try:
    from ubuntutools.config import ubu_email as get_maintainer
except ImportError:
    from .utils import portable_get_maintainer as get_maintainer  # noqa

try:
    rinput = raw_input  # py2
except NameError:
    rinput = input  # py3

log = logging.getLogger(__name__)


class CharmGeneratorException(Exception):
    pass


class CharmGenerator(object):
    """Generate a new Charm on the filesystem"""

    def __init__(self, cmdline_opts):
        self.opts = cmdline_opts
        self.plugin = self._load_plugin()

    def _load_plugin(self):
        """Instantiate and return the plugin defined by the ``template_name``
        entry point.

        """
        for ep in pkg_resources.iter_entry_points('charmtools.templates'):
            if ep.name == self.opts.template:
                return ep.load()()

    def create_charm(self):
        """Gather user configuration and hand it off to the template plugin to
        create the files and directories for the new charm.

        """
        output_path = self._get_output_path()
        if os.path.exists(output_path):
            raise CharmGeneratorException(
                '{} exists. Please move it out of the way.'.format(
                    output_path))
        if not os.access(os.path.dirname(output_path), os.W_OK):
            raise CharmGeneratorException('Unable to write to {}'.format(
                output_path))

        log.info('Generating charm for %s in %s',
                 self.opts.charmname, output_path)

        metadata = self._get_metadata()
        user_config = self._get_user_config()
        user_config.update(metadata=metadata)
        tempdir = self._get_tempdir()
        try:
            self.plugin.create_charm(user_config, tempdir)
            shutil.copytree(tempdir, output_path, symlinks=True)
        finally:
            self._cleanup(tempdir)

    def _get_metadata(self):
        d = {
            'package': self.opts.charmname,
            'maintainer': '%s <%s>' % get_maintainer(),
        }
        d.update(apt_fill(self.opts.charmname))

        return d

    def _get_user_config(self):
        """Get user configuration by prompting for it interactively
        or using predefined defaults.

        """
        config = {}
        for prompt in self.plugin.prompts():
            config[prompt.name] = self._prompt(prompt, config)
        return config

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
            return prompt.validate(prompt.default)
        user_input = rinput(prompt.prompt).strip()
        if not user_input:
            return prompt.validate(prompt.default)
        try:
            return self.plugin.validate_input(user_input, prompt, config)
        except Exception as e:
            print(str(e))
            return self._prompt(prompt, config)

    def _get_output_path(self):
        return os.path.join(self.opts.charmhome, self.opts.charmname)

    def _get_tempdir(self):
        return tempfile.mkdtemp()

    def _cleanup(self, tempdir):
        if os.path.exists(tempdir):
            # not sure how it could actually get to this point without the
            # tempdir existing, but we had some reports, so we should check
            shutil.rmtree(tempdir)
