from __future__ import absolute_import

import os
import re
import hashlib
import email.utils
import six

import colander
import yaml

from stat import ST_MODE
from stat import S_IXUSR

import dict2colander

from charmtools.linter import Linter
from charmtools.utils import validate_display_name

KNOWN_METADATA_KEYS = (
    'name',
    'display-name',
    'summary',
    'docs',
    'maintainer',
    'maintainers',
    'min-juju-version',
    'description',
    'categories',
    'subordinate',
    'provides',
    'requires',
    'format',
    'peers',
    'tags',
    'series',
    'storage',
    'extra-bindings',
    'payloads',
    'terms',
    'resources',
    'devices',
    'deployment',
)

REQUIRED_METADATA_KEYS = (
    'name',
    'summary',
)

KNOWN_RELATION_KEYS = ('interface', 'scope', 'limit', 'optional')

KNOWN_SCOPES = ('global', 'container')

TEMPLATE_PATH = os.path.abspath(os.path.dirname(__file__))

TEMPLATE_README = os.path.join(
    TEMPLATE_PATH, 'templates', 'bash', 'files', 'README.md')

TEMPLATE_ICON = os.path.join(
    TEMPLATE_PATH, 'templates', 'bash', 'files', 'icon.svg')

KNOWN_OPTION_KEYS = set(('description', 'type', 'default'))

KNOWN_OPTION_TYPES = {
    'string': six.string_types[0],
    'int': int,
    'float': float,
    'boolean': bool,
}

ALLOW_NONE_DEFAULT = (six.string_types[0], int, float, bool)


class RelationError(Exception):
    pass


class CharmLinter(Linter):

    # _WINDOWS_HOOKS_EXTS is the list of possible extensions for hooks
    # on Windows. File extensions must be present in Windows ad thus
    # we must specially check for them when linting the hooks.
    _WINDOWS_HOOKS_EXTS = [".ps1", ".cmd", ".bat", ".exe"]

    def check_hook(self, hook, hooks_path, recommended=False):
        hook_path = os.path.join(hooks_path, hook)
        ispscharm = False  # flag to indicate whether PowerShell charm or not.

        # iterate through the possible hook-extension
        # combinations and find the right one:
        for path in [hook_path + ext for ext in self._WINDOWS_HOOKS_EXTS]:
            if os.path.isfile(path):
                hook_path = path
                ispscharm = True
                break

        try:
            mode = os.stat(hook_path)[ST_MODE]

            # NOTE: hooks on Windows are judged as executable depending on
            # their extension; not their mode.
            if (not mode & S_IXUSR) and not ispscharm:
                self.info(hook + " not executable")

            with open(hook_path, 'r') as hook_file:
                count = 0
                for line in hook_file:
                    count += 1
                    hook_warnings = [
                        {'re': re.compile(r"http://169\.254\.169\.254/"),
                         'msg': "hook accesses EC2 metadata service directly"}]
                    for warning in hook_warnings:
                        if warning['re'].search(line):
                            self.warn(
                                "(%s:%d) - %s" %
                                (hook, count, warning['msg']))
            return True

        except OSError:
            if recommended:
                self.info("missing recommended hook " + hook)
            return False

    def check_relation_hooks(self, relations, subordinate, hooks_path):
        template_interfaces = ('interface-name')
        template_relations = ('relation-name')

        for r in relations.items():
            if r[0].startswith('juju-'):
                self.info('juju-* is a reserved relation name')
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
                r + '-relation-changed', hooks_path)
            has_one = has_one or self.check_hook(
                r + '-relation-departed', hooks_path)
            has_one = has_one or self.check_hook(
                r + '-relation-joined', hooks_path)
            has_one = has_one or self.check_hook(
                r + '-relation-broken', hooks_path)

            if not has_one and not subordinate:
                self.info("relation " + r + " has no hooks")

    def check_config_file(self, charm_path):
        config_path = os.path.join(charm_path, 'config.yaml')
        if not os.path.isfile(config_path):
            self.info('File config.yaml not found.')
            return
        try:
            with open(config_path, "rb") as config_file:
                config = yaml.safe_load(config_file.read())
        except Exception as error:
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
            if not re.match(r'^[a-z0-9]+(?:[\w-]*[a-z0-9]+)?$', option_name,
                            flags=re.IGNORECASE):
                self.err('config.yaml: %s does not conform to naming pattern'
                         % option_name)
            if not isinstance(option_value, dict):
                self.err(
                    'config.yaml: data for option %s is not a dict'
                    % option_name)
                continue
            existing_keys = set(option_value)
            missing_keys = KNOWN_OPTION_KEYS - existing_keys
            if missing_keys:
                self.warn(
                    'config.yaml: option %s does not have the keys: %s' % (
                        option_name, ', '.join(sorted(missing_keys))))
            invalid_keys = existing_keys - KNOWN_OPTION_KEYS
            if invalid_keys:
                invalid_keys = sorted([str(key) for key in invalid_keys])
                self.warn(
                    'config.yaml: option %s has unknown keys: %s' % (
                        option_name, ', '.join(invalid_keys)))

            if 'description' in existing_keys:
                if not isinstance(option_value['description'],
                                  six.string_types) or \
                        option_value['description'].strip() == '':
                    self.warn(
                        'config.yaml: description of option %s should be a '
                        'non-empty string' % option_name)
            option_type = option_value.get('type', 'string')
            if option_type not in KNOWN_OPTION_TYPES:
                self.warn('config.yaml: option %s has an invalid type (%s)'
                          % (option_name, option_type))
            elif 'default' in option_value:
                expected_type = KNOWN_OPTION_TYPES[option_type]
                actual_value = option_value['default']
                if actual_value is None:
                    notify = (self.info if expected_type in ALLOW_NONE_DEFAULT
                              else self.warn)
                    notify(
                        'config.yaml: option %s has no default value'
                        % option_name)
                elif not isinstance(actual_value, expected_type):
                    self.err(
                        'config.yaml: type of option %s is specified as '
                        '%s, but the type of the default value is %s'
                        % (option_name, option_type,
                           type(actual_value).__name__))
            else:
                # Nothing to do: the option type is valid but no default
                # value exists.
                pass


class Charm(object):
    def __init__(self, path, linter=None):
        self.charm_path = path
        self.linter = linter or CharmLinter()
        if not self.is_charm():
            raise Exception('Not a Charm')

    def is_charm(self):
        return os.path.isfile(os.path.join(self.charm_path, 'metadata.yaml'))

    def proof(self):
        lint = self.linter
        charm_name = self.charm_path
        if os.path.isdir(charm_name):
            charm_path = charm_name
        else:
            charm_home = os.getenv('CHARM_HOME', '.')
            charm_path = os.path.join(charm_home, charm_name)

        if not os.path.isdir(charm_path):
            lint.crit("%s is not a directory, Aborting" % charm_path)
            return lint.lint, lint.exit_code

        hooks_path = os.path.join(charm_path, 'hooks')
        actions_path = os.path.join(charm_path, 'actions')
        functions_path = os.path.join(charm_path, 'functions')
        yaml_path = os.path.join(charm_path, 'metadata.yaml')
        actions_yaml_file = os.path.join(charm_path, 'actions.yaml')
        functions_yaml_file = os.path.join(charm_path, 'functions.yaml')
        layer_yaml_file = os.path.join(charm_path, 'layer.yaml')
        try:
            yamlfile = open(yaml_path, "rb")
            try:
                charm = yaml.safe_load(yamlfile)
            except Exception as e:
                lint.crit('cannot parse ' + yaml_path + ":" + str(e))
                return lint.lint, lint.exit_code
            yamlfile.close()

            proof_extensions = {}
            try:
                with open(layer_yaml_file, "rb") as yamlfile:
                    try:
                        layer_data = yaml.safe_load(yamlfile)
                        proof_extensions.update(layer_data.get('proof', {}))
                    except Exception as e:
                        lint.warn('cannot parse {}: {}'.format(layer_yaml_file,
                                                               str(e)))
            except Exception:
                # not all charms have a layer.yaml
                pass

            validate_metadata_keys(charm, lint)

            charm_basename = os.path.basename(charm_path)
            if charm.get('name') != charm_basename:
                msg = (
                    "metadata name (%s) must match directory name (%s)"
                    " exactly for local deployment.") % (charm.get('name'),
                                                         charm_basename)
                lint.info(msg)

            # summary should be short
            if len(charm.get('summary', '')) > 72:
                lint.warn('summary should be less than 72')

            validate_display_name(charm, lint)
            validate_maintainer(charm, lint)
            validate_categories_and_tags(charm, lint)
            validate_storage(charm, lint, proof_extensions.get('storage'))
            validate_devices(charm, lint, proof_extensions.get('devices'))
            validate_series(charm, lint)
            validate_min_juju_version(charm, lint)
            validate_extra_bindings(charm, lint)
            validate_payloads(charm, lint, proof_extensions.get('payloads'))
            validate_terms(charm, lint)
            validate_resources(charm, lint, proof_extensions.get('resources'))
            validate_deployment(charm, lint,
                                proof_extensions.get('deployment'))

            if not os.path.exists(os.path.join(charm_path, 'icon.svg')):
                lint.info("No icon.svg file.")
            else:
                # should have an icon.svg
                template_sha1 = hashlib.sha1()
                icon_sha1 = hashlib.sha1()
                try:
                    with open(TEMPLATE_ICON, 'rb') as ti:
                        template_sha1.update(ti.read())
                        icon_file = os.path.join(charm_path, 'icon.svg')
                        with open(icon_file, 'rb') as ci:
                            icon_sha1.update(ci.read())
                    if template_sha1.hexdigest() == icon_sha1.hexdigest():
                        lint.info("Includes template icon.svg file.")
                except IOError as e:
                    lint.info(
                        "Error while opening %s (%s)" %
                        (e.filename, e.strerror))

            # Must have a hooks dir
            if not os.path.exists(hooks_path):
                lint.info("no hooks directory")

            # Must have a copyright file
            if not os.path.exists(os.path.join(charm_path, 'copyright')):
                lint.warn("no copyright file")

            # should have a readme
            root_files = os.listdir(charm_path)
            found_readmes = set()
            for filename in root_files:
                if filename.upper().find('README') != -1:
                    found_readmes.add(filename)
            if len(found_readmes):
                if 'README.ex' in found_readmes:
                    lint.warn("Includes template README.ex file")
                try:
                    with open(TEMPLATE_README) as tr:
                        bad_lines = []
                        for line in tr:
                            if len(line) >= 40:
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
                                        err_msg = ('%s includes boilerplate: '
                                                   '%s')
                                        lint.warn(err_msg % (readme, l))
                except IOError as e:
                    lint.warn(
                        "Error while opening %s (%s)" %
                        (e.filename, e.strerror))
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
                    lint.info("all charms should provide at least one thing")

            if subordinate:
                try:
                    requires = charm.get('requires')
                    if requires is not None:
                        found_scope_container = False
                        for rel in six.itervalues(requires):
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
                    lint.check_relation_hooks(requires, subordinate,
                                              hooks_path)

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

            lint.check_hook('install', hooks_path, recommended=True)
            lint.check_hook('start', hooks_path, recommended=True)
            lint.check_hook('stop', hooks_path, recommended=True)
            if os.path.exists(os.path.join(charm_path, 'config.yaml')):
                lint.check_hook('config-changed', hooks_path, recommended=True)
            else:
                lint.check_hook('config-changed', hooks_path)

            if os.path.exists(actions_yaml_file):
                # TODO: remove action code when it's deprecated.
                with open(actions_yaml_file, "rb") as f:
                    try:
                        actions = yaml.safe_load(f.read())
                        validate_actions(actions, actions_path, lint)
                    except Exception as e:
                        lint.crit('cannot parse {}: {}'.format(
                            actions_yaml_file, e))
            elif os.path.exists(functions_yaml_file):
                with open(functions_yaml_file, "rb") as f:
                    try:
                        functions = yaml.safe_load(f.read())
                        validate_functions(functions, functions_path, lint)
                    except Exception as e:
                        lint.crit('cannot parse {}: {}'.format(
                            functions_yaml_file, e))

        except IOError:
            lint.err("could not find metadata file for " + charm_name)
            lint.exit_code = -1

        # Should not have autogen test
        if os.path.exists(os.path.join(charm_path, 'tests', '00-autogen')):
            lint.warn('Includes template test file, tests/00-autogen')

        rev_path = os.path.join(charm_path, 'revision')
        if os.path.exists(rev_path):
            with open(rev_path, 'r') as rev_file:
                content = rev_file.read().rstrip()
                try:
                    int(content)
                except ValueError:
                    lint.err("revision file contains non-numeric data")

        lint.check_config_file(charm_path)
        return lint.lint, lint.exit_code

    def metadata(self):
        metadata = None
        with open(os.path.join(self.charm_path, 'metadata.yaml'), "rb") as f:
            metadata = yaml.safe_load(f.read())

        return metadata

    def promulgate(self):
        pass


class StrictMapping(colander.Mapping):
    def __init__(self):
        super(StrictMapping, self).__init__(unknown='raise')


class Boolean(object):
    def deserialize(self, node, cstruct):
        if cstruct is colander.null:
            return colander.null
        if isinstance(cstruct, bool):
            cstruct = str(cstruct).lower()
        if cstruct not in ('true', 'false'):
            raise colander.Invalid(
                node, '"%s" is not one of true, false' % cstruct)


class StringOrEmpty(colander.String):
    """
    Subclass of colander.String that defaults allow_empty to True.
    """
    def __init__(self, encoding=None, allow_empty=True):
        super(StringOrEmpty, self).__init__(encoding, allow_empty)


class SchemaBuilder(dict2colander.SchemaBuilder):
    def __init__(self):
        super(SchemaBuilder, self).__init__()
        self.add_type('Mapping', StrictMapping)
        self.add_type('Boolean', Boolean)
        # override String type to default to allow empty
        self.add_type('String', StringOrEmpty)

    def _get_validation_schema(self):
        # override validation schema to ensure that the `missing`
        # field allows empty strings
        root = super(SchemaBuilder, self)._get_validation_schema()
        node_for_missing = [node
                            for node in root.children
                            if node.name == 'missing'][0]
        node_for_missing.typ = StringOrEmpty()
        return root


class ResourceItem(colander.MappingSchema):
    def schema_type(self, **kw):
        return StrictMapping()

    type_ = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(['file', 'oci-image']),
        name='type',
    )
    filename = colander.SchemaNode(
        colander.String(),
        missing=colander.drop,
    )
    description = colander.SchemaNode(
        colander.String(allow_empty=True),
        missing='',
    )


class DevicesItem(colander.MappingSchema):
    def schema_type(self, **kw):
        return StrictMapping()

    type_ = colander.SchemaNode(
        colander.String(),
        name='type',
    )

    count = colander.SchemaNode(
        colander.Integer(),
        missing=1,
    )


class DeploymentItem(colander.MappingSchema):
    def schema_type(self, **kw):
        return StrictMapping()

    type_ = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(['stateless', 'stateful', 'daemon']),
        name='type',
        missing='',
    )

    service = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(['loadbalancer', 'cluster', 'omit']),
        name='service',
    )

    min_version = colander.SchemaNode(
        colander.String(),
        name='min-version',
        missing='',
    )


class StorageItem(colander.MappingSchema):
    def schema_type(self, **kw):
        return StrictMapping()

    type_ = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(['filesystem', 'block']),
        name='type',
    )
    description = colander.SchemaNode(
        colander.String(),
        missing='',
    )
    shared = colander.SchemaNode(
        Boolean(),
        missing=False,
    )
    read_only = colander.SchemaNode(
        Boolean(),
        missing=False,
        name='read-only',
    )
    minimum_size = colander.SchemaNode(
        colander.String(),
        validator=colander.Regex(
            r'^\d+[MGTP]?$',
            msg='must be a number followed by an optional '
                'M/G/T/P, e.g. 100M'
        ),
        missing='',
        name='minimum-size',
    )
    location = colander.SchemaNode(
        colander.String(),
        missing='',
    )

    @colander.instantiate(missing={})
    class multiple(colander.MappingSchema):
        def schema_type(self, **kw):
            return StrictMapping()

        range_ = colander.SchemaNode(
            colander.String(),
            validator=colander.Regex(
                r'^\d+-?(\d+)?$',
                msg='supported formats are: m (a fixed number), '
                    'm-n (an explicit range), and m- (a minimum number)'
            ),
            name='range',
        )


class PayloadItem(colander.MappingSchema):
    def schema_type(self, **kw):
        return StrictMapping()

    type_ = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(['kvm', 'docker']),
        name='type',
    )


def _try_proof_extensions(e, proof_extensions):
    if not proof_extensions:
        raise e
    proof_extensions = {'name': 'extensions',
                        'type': 'Mapping',
                        'subnodes': proof_extensions}
    new_e = colander.Invalid(e.node)
    for child_e in e.children:
        if isinstance(child_e, colander.UnsupportedFields):
            try:
                schema_builder = SchemaBuilder()
                schema = schema_builder.dict_to_schema(proof_extensions)
                schema.deserialize(child_e.fields)
            except colander.Invalid as ext_e:
                new_e.add(ext_e)
        else:
            new_e.add(child_e)
    if new_e.children:
        raise new_e


def validate_terms(charm, linter):
    """Validate terms in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    if 'terms' not in charm:
        return

    if not isinstance(charm['terms'], list):
        linter.err('terms: must be a list of term ids')


def validate_resources(charm, linter, proof_extensions=None):
    """Validate resources in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written
    :param proof_extensions: optional dict of extensions to proof which will
        only be applied to otherwise unrecognized fields; this allows for
        layer-defined annotations to pass proof

    """
    if 'resources' not in charm:
        return

    if (not isinstance(charm['resources'], dict) or
            not charm['resources']):
        linter.err('resources: must be a dictionary of resource definitions')
        return

    schema = colander.SchemaNode(colander.Mapping())
    for resource_def in charm['resources']:
        schema.add(ResourceItem(name=resource_def))

    try:
        try:
            schema.deserialize(charm['resources'])
        except colander.Invalid as e:
            _try_proof_extensions(e, proof_extensions)
    except colander.Invalid as e:
        for k, v in e.asdict().items():
            linter.err('resources.{}: {}'.format(k, v))


def validate_deployment(charm, linter, proof_extensions=None):
    """Validate deployment in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """

    deployment = charm.get('deployment', {})
    if deployment == {}:
        return

    if not isinstance(deployment, dict):
        linter.err('deployment: must be a dict of config')
        return

    deployment = dict(deployment=deployment)
    schema = colander.SchemaNode(colander.Mapping())
    for item in deployment:
        schema.add(DeploymentItem(name=item))

    try:
        try:
            schema.deserialize(deployment)
        except colander.Invalid as e:
            _try_proof_extensions(e, proof_extensions)
    except colander.Invalid as e:
        for k, v in e.asdict().items():
            linter.err('deployment.{}: {}'.format(k, v))


def validate_extra_bindings(charm, linter):
    """Validate extra-bindings in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    if 'extra-bindings' not in charm:
        return

    if not isinstance(charm['extra-bindings'], dict):
        linter.err('extra-bindings: must be a dictionary')


def validate_min_juju_version(charm, linter):
    """Validate min-juju-version in charm metadata.

    Must match the regex and be 2.0.0 or greater.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    if 'min-juju-version' not in charm:
        return

    pattern = r'(\d{1,9})\.(\d{1,9})(?:\.|-([a-z]+))(\d{1,9})(\.\d{1,9})?'
    match = re.match(pattern, str(charm['min-juju-version']))
    if not match:
        linter.err('min-juju-version: invalid format, try X.Y.Z')
        return

    if int(match.group(1)) < 2:
        linter.err(
            'min-juju-version: invalid version, must be 2.0.0 or greater')


def validate_series(charm, linter):
    """Validate supported series list in charm metadata.

    We don't validate the actual series names because:

    1. `charm push` does that anyway
    2. our list of valid series would be constantly falling out-of-date

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    if 'series' not in charm:
        linter.err('missing series: must be a list of series names')
    elif not isinstance(charm['series'], list):
        linter.err('series: must be a list of series names')


def validate_storage(charm, linter, proof_extensions=None):
    """Validate storage configuration in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written
    :param proof_extensions: optional dict of extensions to proof which will
        only be applied to otherwise unrecognized fields; this allows for
        layer-defined annotations to pass proof

    """
    if 'storage' not in charm:
        return

    if (not isinstance(charm['storage'], dict) or
            not charm['storage']):
        linter.err('storage: must be a dictionary of storage definitions')
        return

    schema = colander.SchemaNode(colander.Mapping())
    for storage_def in charm['storage']:
        schema.add(StorageItem(name=storage_def))

    try:
        try:
            schema.deserialize(charm['storage'])
        except colander.Invalid as e:
            _try_proof_extensions(e, proof_extensions)
    except colander.Invalid as e:
        for k, v in e.asdict().items():
            linter.err('storage.{}: {}'.format(k, v))


def validate_devices(charm, linter, proof_extensions=None):
    """Validate devices configuration in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written
    :param proof_extensions: optional dict of extensions to proof which will
        only be applied to otherwise unrecognized fields; this allows for
        layer-defined annotations to pass proof

    """
    devices = charm.get('devices', {})
    if devices == {}:
        return

    if not isinstance(devices, dict):
        linter.err('devices: must be a dictionary of device definitions')
        return

    schema = colander.SchemaNode(colander.Mapping())
    for dev in devices:
        schema.add(DevicesItem(name=dev))

    try:
        try:
            schema.deserialize(devices)
        except colander.Invalid as e:
            _try_proof_extensions(e, proof_extensions)
    except colander.Invalid as e:
        for k, v in e.asdict().items():
            linter.err('devices.{}: {}'.format(k, v))


def validate_payloads(charm, linter, proof_extensions=None):
    """Validate paylaod configuration in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written
    :param proof_extensions: optional dict of extensions to proof which will
        only be applied to otherwise unrecognized fields; this allows for
        layer-defined annotations to pass proof

    """
    if 'payloads' not in charm:
        return

    if (not isinstance(charm['payloads'], dict) or
            not charm['payloads']):
        linter.err('payloads: must be a dictionary of payload definitions')
        return

    schema = colander.SchemaNode(colander.Mapping())
    for payload_def in charm['payloads']:
        schema.add(PayloadItem(name=payload_def))

    try:
        try:
            schema.deserialize(charm['payloads'])
        except colander.Invalid as e:
            _try_proof_extensions(e, proof_extensions)
    except colander.Invalid as e:
        for k, v in e.asdict().items():
            linter.err('payloads.{}: {}'.format(k, v))


def validate_actions(actions, action_hooks, linter):
    """Validate actions in a charm.

    :param actions: dict of charm actions parsed from actions.yaml
    :param action_hooks: path of charm's /actions/ directory
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """

    if not actions:
        return

    if not isinstance(actions, dict):
        linter.err('actions: must be a dictionary of json schemas')
        return

    # TODO: Schema validation
    for k in actions:
        if k.startswith('juju'):
            linter.err('actions.{}: juju is a reserved namespace'.format(k))
            continue
        h = os.path.join(action_hooks, k)
        if not os.path.isfile(h):
            linter.warn('actions.{0}: actions/{0} does not exist'.format(k))
        elif not os.access(h, os.X_OK):
            linter.err('actions.{0}: actions/{0} is not executable'.format(k))


def validate_functions(functions, function_hooks, linter):
    """Validate functions in a charm.

    :param functions: dict of charm functions parsed from functions.yaml
    :param function_hooks: path of charm's /functions/ directory
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """

    if not functions:
        return

    if not isinstance(functions, dict):
        linter.err('functions: must be a dictionary of json schemas')
        return

    # TODO: Schema validation
    for k in functions:
        if k.startswith('juju'):
            linter.err('functions.{}: juju is a reserved namespace'.format(k))
            continue
        h = os.path.join(function_hooks, k)
        if not os.path.isfile(h):
            linter.warn('functions.{0}: functions/{0} does not exist'.format(k))
        elif not os.access(h, os.X_OK):
            linter.err('functions.{0}: functions/{0} is not executable'.format(k))


def validate_maintainer(charm, linter):
    """Validate maintainer info in charm metadata.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    if 'maintainer' in charm and 'maintainers' in charm:
        linter.err(
            'Charm must not have both maintainer and maintainers fields')
        return

    if 'maintainer' not in charm and 'maintainers' not in charm:
        linter.err(
            'Charm must have either a maintainer or maintainers field')
        return

    maintainers = []
    if 'maintainer' in charm:
        if isinstance(charm['maintainer'], list):
            linter.err('Maintainer field must not be a list')
            return
        maintainers = [charm['maintainer']]
    elif 'maintainers' in charm:
        if not isinstance(charm['maintainers'], list):
            linter.err('Maintainers field must be a list')
            return
        maintainers = charm['maintainers']

    for maintainer in maintainers:
        (name, address) = email.utils.parseaddr(maintainer)
        if not (name and address):
            linter.warn(
                'Maintainer format should be "Name <Email>", '
                'not "%s"' % maintainer)


def validate_categories_and_tags(charm, linter):
    if 'categories' not in charm and 'tags' not in charm:
        linter.warn('Metadata missing required field "tags"')
        return

    if 'tags' in charm:
        tags = charm['tags']
        if type(tags) != list or tags == []:
            linter.warn('Metadata field "tags" must be a non-empty list')

    if 'categories' in charm:
        categories = charm['categories']
        if type(categories) != list or categories == []:
            # The category names are not validated because they may
            # change.
            linter.warn(
                'Categories metadata must be a list of one or more of: '
                'applications, app-servers, databases, file-servers, '
                'cache-proxy, misc')
        linter.warn(
            'Categories are being deprecated in favor of tags. '
            'Please rename the "categories" field to "tags".'
        )


def validate_metadata_keys(charm, linter):
    """Validate keys in metadata.yaml.

    :param charm: dict of charm metadata parsed from metadata.yaml
    :param linter: :class:`CharmLinter` object to which info/warning/error
        messages will be written

    """
    for key in charm.keys():
        if key not in KNOWN_METADATA_KEYS:
            linter.info("Unknown root metadata field (%s)" % key)

    for key in REQUIRED_METADATA_KEYS:
        if key not in charm:
            linter.err("Missing required metadata field (%s)" % key)
