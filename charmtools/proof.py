#!/usr/bin/python

#    Copyright (C) 2011 - 2012  Canonical Ltd.
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

import argparse
import email.utils
import os
import re
from stat import ST_MODE
from stat import S_IXUSR
import sys
import yaml
import hashlib

KNOWN_METADATA_KEYS = ['name',
                       'summary',
                       'maintainer',
                       'description',
                       'categories',
                       'subordinate',
                       'provides',
                       'requires',
                       'format',
                       'peers']

KNOWN_RELATION_KEYS = ['interface', 'scope', 'limit', 'optional']

KNOWN_SCOPES = ['global', 'container']

TEMPLATE_PATH = os.path.abspath(os.path.dirname(__file__))

TEMPLATE_README = os.path.join(TEMPLATE_PATH, 'templates', 'charm',
                               'README.ex')

TEMPLATE_ICON = os.path.join(TEMPLATE_PATH, 'templates', 'charm', 'icon.svg')

KNOWN_OPTION_KEYS = set(('description', 'type', 'default'))

REQUIRED_OPTION_KEYS = set(('description', ))

KNOWN_OPTION_TYPES = {
    'str': basestring,
    'int': int,
    'float': float,
    'boolean': bool,
}


class RelationError(Exception):
    pass


class Linter(object):

    def __init__(self):
        self.lint = []
        self.exit_code = 0

    def crit(self, msg):
        """Called when checking cannot continue."""
        self.err("FATAL: " + msg)

    def err(self, msg):
        global EXIT_CODE
        self.lint.append("E: " + msg)
        if self.exit_code < 200:
            self.exit_code = 200

    def info(self, msg):
        """Ignorable but sometimes useful."""
        self.lint.append("I: " + msg)

    def warn(self, msg):
        global EXIT_CODE
        self.lint.append("W: " + msg)
        if self.exit_code < 100:
            self.exit_code = 100

    def check_hook(self, hook, hooks_path, required=True, recommended=False):
        hook_path = os.path.join(hooks_path, hook)

        try:
            mode = os.stat(hook_path)[ST_MODE]
            if not mode & S_IXUSR:
                self.warn(hook + " not executable")
            with open(hook_path, 'r') as hook_file:
                count = 0
                for line in hook_file:
                    count += 1
                    hook_warnings = [
                        {'re': re.compile("http://169\.254\.169\.254/"),
                         'msg': "hook accesses EC2 metadata service directly"}]
                    for warning in hook_warnings:
                        if warning['re'].search(line):
                            self.warn(
                                "(%s:%d) - %s" %
                                (hook, count, warning['msg']))
            return True

        except OSError:
            if required:
                self.err("missing hook " + hook)
            elif recommended:
                self.warn("missing recommended hook " + hook)
            return False

    def check_relation_hooks(self, relations, subordinate, hooks_path):
        template_interfaces = ('interface-name')
        template_relations = ('relation-name')

        for r in relations.items():
            if type(r[1]) != dict:
                self.err("relation %s is not a map" % (r[0]))
            else:
                if 'scope' in r[1]:
                    scope = r[1]['scope']
                    if scope not in KNOWN_SCOPES:
                        self.err("Unknown scope found in relation %s - (%s)" %
                                 (r[0], scope))
                if 'interface' in r[1]:
                    interface = r[1]['interface']
                    if interface in template_interfaces:
                        self.err("template interface names should be "
                                 "changed: " + interface)
                else:
                    self.err("relation missing interface")
                for key in r[1].keys():
                    if key not in KNOWN_RELATION_KEYS:
                        self.err(
                            "Unknown relation field in relation %s - (%s)" %
                            (r[0], key))

            r = r[0]

            if r in template_relations:
                self.err("template relations should be renamed to fit "
                         "charm: " + r)

            has_one = False
            has_one = has_one or self.check_hook(
                r + '-relation-changed', hooks_path, required=False)
            has_one = has_one or self.check_hook(
                r + '-relation-departed', hooks_path, required=False)
            has_one = has_one or self.check_hook(
                r + '-relation-joined', hooks_path, required=False)
            has_one = has_one or self.check_hook(
                r + '-relation-broken', hooks_path, required=False)

            if not has_one and not subordinate:
                self.info("relation " + r + " has no hooks")

    def check_config_file(self, charm_path):
        config_path = os.path.join(charm_path, 'config.yaml')
        if not os.path.isfile(config_path):
            self.warn('File config.yaml not found.')
            return
        try:
            with open(config_path) as config_file:
                config = yaml.load(config_file.read())
        except Exception, error:
            self.err('Cannot parse config.yaml: %s' % error)
            return
        if not isinstance(config, dict):
            self.err('config.yaml not parsed into a dictionary.')
            return
        if 'options' not in config:
            self.err('config.yaml must have an "options" key.')
            return
        if len(config) > 1:
            wrong_keys = sorted(config)
            wrong_keys.pop(wrong_keys.index('options'))
            self.warn('Ignored keys in config.yaml: %s' % wrong_keys)

        options = config['options']
        if not isinstance(options, dict):
            self.err(
                'config.yaml: options section is not parsed as a dictionary')
            return

        for option_name, option_value in options.items():
            if not isinstance(option_value, dict):
                self.err(
                    'config.yaml: data for option %s is not a dict'
                    % option_name)
                continue
            existing_keys = set(option_value)
            missing_keys = KNOWN_OPTION_KEYS - existing_keys
            missing_required_keys = REQUIRED_OPTION_KEYS & missing_keys
            missing_optional_keys = missing_keys - missing_required_keys
            if missing_required_keys:
                self.err(
                    'config.yaml: option %s does not have the required keys: '
                    '%s' % (
                        option_name, ', '.join(sorted(missing_required_keys))))
            if missing_optional_keys:
                self.warn(
                    'config.yaml: option %s does not have the optional keys: '
                    '%s' % (
                        option_name, ', '.join(sorted(missing_optional_keys))))
            invalid_keys = existing_keys - KNOWN_OPTION_KEYS
            if invalid_keys:
                invalid_keys = [str(key) for key in sorted(invalid_keys)]
                self.warn(
                    'config.yaml: option %s as unknown keys: %s' % (
                        option_name, ', '.join(invalid_keys)))

            if 'description' in existing_keys:
                if not isinstance(option_value['description'], basestring):
                    self.warn(
                        'config.yaml: description of option %s should be a '
                        'string' % option_name)
            option_type = option_value.get('type', 'str')
            if option_type not in KNOWN_OPTION_TYPES:
                self.warn('config.yaml: option %s has an invalid type (%s)'
                          % (option_name, option_type))
            elif 'default' in option_value:
                expected_type = KNOWN_OPTION_TYPES[option_value['type']]
                if not isinstance(option_value['default'], expected_type):
                    self.err(
                        'config.yaml: type of option %s is specified as '
                        '%s, but the type of the default value is %s'
                        % (option_name, option_value['type'],
                           type(option_value['default']).__name__))
            else:
                # Nothing to do: the option type is valid but no default
                # value exists.
                pass


def get_args():
    parser = argparse.ArgumentParser(
        description='Performs static analysis on charms')
    parser.add_argument('charm_name', nargs='?',
                        help='path of charm dir to check. Defaults to PWD')
    args = parser.parse_args()

    if args.charm_name:
        charm_name = args.charm_name
    else:
        charm_name = os.getcwd()

    return charm_name


def run(charm_name):
    lint = Linter()
    if os.path.isdir(charm_name):
        charm_path = charm_name
    else:
        charm_home = os.getenv('CHARM_HOME', '.')
        charm_path = os.path.join(charm_home, charm_name)

    if not os.path.isdir(charm_path):
        lint.crit("%s is not a directory, Aborting" % charm_path)
        return lint.lint, lint.exit_code

    hooks_path = os.path.join(charm_path, 'hooks')
    yaml_path = os.path.join(charm_path, 'metadata.yaml')
    try:
        yamlfile = open(yaml_path, 'r')
        try:
            charm = yaml.load(yamlfile)
        except Exception as e:
            lint.crit('cannot parse ' + yaml_path + ":" + str(e))
            return lint.lint, lint.exit_code

        yamlfile.close()

        for key in charm.keys():
            if key not in KNOWN_METADATA_KEYS:
                lint.err("Unknown root metadata field (%s)" % key)

        charm_basename = os.path.basename(charm_path)
        if charm['name'] != charm_basename:
            warn_msg = ("metadata name (%s) must match directory name (%s) "
                        "exactly for local deployment.") % (
                            charm['name'], charm_basename)
            lint.warn(warn_msg)

        # summary should be short
        if len(charm['summary']) > 72:
            lint.warn('summary sould be less than 72')

        # need a maintainer field
        if 'maintainer' not in charm:
            lint.err('Charms need a maintainer (See RFC2822) - Name <email>')
        else:
            if type(charm['maintainer']) == list:  # It's a list
                maintainers = charm['maintainer']
            else:
                maintainers = [charm['maintainer']]
            for maintainer in maintainers:
                (name, address) = email.utils.parseaddr(maintainer)
                formatted = email.utils.formataddr((name, address))
                if formatted != maintainer:
                    warn_msg = ("Maintainer address should contain a "
                                "real-name and email only. [%s]" % (
                                    formatted))
                    lint.warn(warn_msg)

        if 'categories' not in charm:
            lint.warn('Metadata is missing categories.')
        else:
            categories = charm['categories']
            if type(categories) != list or categories == []:
                # The category names are not validated because jujucharms.com
                # may change them.
                lint.warn(
                    'Categories metadata must be a list of one or more of: '
                    'applications, app-servers, databases, file-servers, '
                    'cache-proxy, misc')

        if not os.path.exists(os.path.join(charm_path, 'icon.svg')):
            lint.warn("No icon.svg file.")
        else:
            # should have an icon.svg
            template_sha1 = hashlib.sha1()
            icon_sha1 = hashlib.sha1()
            try:
                with open(TEMPLATE_ICON) as ti:
                    template_sha1.update(ti.read())
                    with open(os.path.join(charm_path, 'icon.svg')) as ci:
                        icon_sha1.update(ci.read())
                if template_sha1.hexdigest() == icon_sha1.hexdigest():
                    lint.err("Includes template icon.svg file.")
            except IOError as e:
                lint.err(
                    "Error while opening %s (%s)" % (e.filename, e.strerror))

        # Must have a hooks dir
        if not os.path.exists(hooks_path):
            lint.err("no hooks directory")

        # Must have a copyright file
        if not os.path.exists(os.path.join(charm_path, 'copyright')):
            lint.err("no copyright file")

        # should have a readme
        root_files = os.listdir(charm_path)
        found_readmes = set()
        for filename in root_files:
            if filename.upper().find('README') != -1:
                found_readmes.add(filename)
        if len(found_readmes):
            if 'README.ex' in found_readmes:
                lint.err("Includes template README.ex file")
            try:
                with open(TEMPLATE_README) as tr:
                    bad_lines = []
                    for line in tr:
                        if len(line) >= 25:
                            bad_lines.append(line.strip())
                    for readme in found_readmes:
                        readme_path = os.path.join(charm_path, readme)
                        with open(readme_path) as r:
                            readme_content = r.read()
                            lc = 0
                            for l in bad_lines:
                                if not len(l):
                                    continue
                                lc += 1
                                if l in readme_content:
                                    err_msg = ('%s Includes boilerplate '
                                               'README.ex line %d')
                                    lint.err(err_msg % (readme, lc))
            except IOError as e:
                lint.err(
                    "Error while opening %s (%s)" % (e.filename, e.strerror))
        else:
            lint.warn("no README file")

        subordinate = charm.get('subordinate', False)
        if type(subordinate) != bool:
            lint.err("subordinate must be a boolean value")

        # All charms should provide at least one thing
        provides = charm.get('provides')
        if provides is not None:
            lint.check_relation_hooks(provides, subordinate, hooks_path)
        else:
            if not subordinate:
                lint.warn("all charms should provide at least one thing")

        if subordinate:
            try:
                requires = charm.get('requires')
                if requires is not None:
                    found_scope_container = False
                    for rel_name, rel in requires.iteritems():
                        if 'scope' in rel:
                            if rel['scope'] == 'container':
                                found_scope_container = True
                                break
                    if not found_scope_container:
                        raise RelationError
                else:
                    raise RelationError
            except RelationError:
                lint.err("subordinates must have at least one scope: "
                         "container relation")
        else:
            requires = charm.get('requires')
            if requires is not None:
                lint.check_relation_hooks(requires, subordinate, hooks_path)

        peers = charm.get('peers')
        if peers is not None:
            lint.check_relation_hooks(peers, subordinate, hooks_path)

        if 'revision' in charm:
            lint.warn("Revision should not be stored in metadata.yaml "
                      "anymore. Move it to the revision file")
            # revision must be an integer
            try:
                x = int(charm['revision'])
                if x < 0:
                    raise ValueError
            except (TypeError, ValueError):
                lint.warn("revision should be a positive integer")

        lint.check_hook('install', hooks_path)
        lint.check_hook('start', hooks_path, required=False, recommended=True)
        lint.check_hook('stop', hooks_path, required=False, recommended=True)
        lint.check_hook('config-changed', hooks_path, required=False)
    except IOError:
        lint.err("could not find metadata file for " + charm_name)
        lint.exit_code = -1

    rev_path = os.path.join(charm_path, 'revision')
    if not os.path.exists(rev_path):
        lint.err("revision file in root of charm is required")
    else:
        with open(rev_path, 'r') as rev_file:
            content = rev_file.read().rstrip()
            try:
                int(content)
            except ValueError:
                lint.err("revision file contains non-numeric data")

    lint.check_config_file(charm_path)
    return lint.lint, lint.exit_code


def main():
    charm_name = get_args()
    lint, exit_code = run(charm_name)
    if lint:
        print "\n".join(lint)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
