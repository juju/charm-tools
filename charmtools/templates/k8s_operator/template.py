#!/usr/bin/env python3
#    Copyright (C) 2010  Canonical Ltd.
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
"""Template for creating a charm based on the Operator Charm framework."""

import datetime
import logging
import os
import os.path as path
import shutil
import subprocess
import tempfile
import time
from stat import ST_MODE

from charmtools.generators import CharmTemplate
from charmtools.generators.prompt import PromptList
from Cheetah.Template import Template

log = logging.getLogger(__name__)


class OperatorPythonCharmTemplate(CharmTemplate):
    """Create an operator charm."""

    _REMOVE_FILES = [".git", ".gitmodules"]
    _TEMPLATE_URL = "https://github.com/chris-sanders/template-k8s-operator.git"

    def prompts(self):
        """Implement prompts for user input."""
        promptlist = PromptList(
            {
                "friendly_name": {
                    "prompt": "User-friendly name for this charm:",
                    "default": None,
                },
                "dev_email": {"prompt": "Developer contact email:", "default": None,},
                "dev_name": {"prompt": "Developer name:", "default": None,},
                "bug_tracker": {
                    "prompt": "URL where bugs can be filed for this Charm:",
                    "default": "https://launchpad.net/amazing-charm",
                },
            }
        )

        return promptlist

    def create_charm(self, config, output_dir):
        """Create the new charm directory and replace template variables."""
        config["metadata"]["package"] = config["metadata"]["package"].lower()
        self._clone_template(config, output_dir)

        for root, dirs, files in os.walk(output_dir, topdown=True):
            for outfile in files:
                if self.skip_template(outfile):
                    continue

                self._template_file(config, path.join(root, outfile))

        self._setup_git_repo(output_dir)
        self._setup_env(output_dir)
        self._add_submodule(output_dir, "https://github.com/johnsca/resource-oci-image.git")
        self._git_commit(
            output_dir,
            msg="Initial commit by charm-template using k8s operator template.",
        )

    def _template_file(self, config, outfile):
        if path.islink(outfile):
            return

        # Add configurations to simplify the templates
        config["class"] = "{}Charm".format(
            "".join(
                char for char in config["friendly_name"].title() if not char.isspace()
            )
        )
        now = datetime.datetime.now()
        config["year"] = now.year

        mode = os.stat(outfile)[ST_MODE]
        template = Template(file=outfile, searchList=(config))
        output = tempfile.NamedTemporaryFile(dir=path.dirname(outfile), delete=False)
        os.chmod(output.name, mode)
        output.write(str(template).encode())
        output.close()
        backupname = outfile + str(time.time())
        os.rename(outfile, backupname)
        os.rename(output.name, outfile)
        os.unlink(backupname)

    def _clone_template(self, config, output_dir):
        cmd = "git clone {} {}".format(self._TEMPLATE_URL, output_dir)

        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error has occurred whilst attempting to clone"
                "the charm template. Please make sure you have git"
                "installed on your system.\n"
                + str(e)
            )

        # iterate and remove all the unwanted files from the git repo:

        for item in [path.join(output_dir, i) for i in self._REMOVE_FILES]:
            if not path.exists(item):
                continue

            if path.isdir(item) and not path.islink(item):
                shutil.rmtree(item)
            else:
                os.remove(item)

    def _setup_git_repo(self, output_dir):
        """Setup a git repo for the charm."""
        cmd = "git -C {} init".format(output_dir)

        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error has occurred whilst attempting to create"
                "a git repository for the new charm:\n{}".format(str(e))
            )

    def _setup_env(self, output_dir):
        """Setup the env directory."""
        cmd = "pip3 install --target={} -r {}".format(
            output_dir + "/env", output_dir + "/requirements.txt"
        )
        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error was encountered when attempting to install"
                "the env:\n{}".format(str(e))
            )


    def _add_submodule(self, output_dir, remote, branch=None):
        """Add a submodule."""

        if branch:
            cmd = "git -C {} submodule add -b {} {}".format(
                output_dir + "/mod", branch, remote
            )
        else:
            cmd = "git -C {} submodule add {}".format(output_dir + "/mod", remote)

        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error was encountered when attempting to add"
                "the Submodule {}:\n{}".format(remote, str(e))
            )

    def _git_commit(self, output_dir, msg="Initial commit"):
        """Commit the git repository."""
        cmd = "git -C {} add .".format(output_dir,)

        try:
            subprocess.check_call(cmd.split())
        except OSError as e:
            raise Exception(
                "The below error has occurred whilst attempting to add files"
                "to the git repository for the new charm:\n{}".format(str(e))
            )

        cmd = "git -C {} commit -am {}".format(output_dir, msg,)

        try:
            subprocess.check_call(cmd.split(maxsplit=5))
        except OSError as e:
            raise Exception(
                "The below error has occurred whilst attempting to commit"
                "to the git repository for the new charm:\n{}".format(str(e))
            )

    def skip_template(self, filename):
        """Skip templates which match certain file patterns."""

        return (
            filename.startswith(".")
            or filename in ("Makefile",)
            or filename.endswith(".pyc")
        )
