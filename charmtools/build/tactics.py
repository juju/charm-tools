import json
import jsonschema
import logging
import os
import tempfile

from path import path
from ruamel import yaml
from charmtools import utils
from charmtools.build.errors import BuildError

log = logging.getLogger(__name__)


class Tactic(object):
    """
    Tactics are first considered in the context of the config layer being
    called the config layer will attempt to (using its author provided info)
    create a tactic for a given file. That will later be intersected with any
    later layers to create a final single plan for each element of the output
    charm.

    Callable that will implement some portion of the charm composition
    Subclasses should implement __str__ and __call__ which should take whatever
    actions are needed.
    """
    kind = "static"  # used in signatures

    @classmethod
    def get(cls, entity, target, layer, next_config, existing_tactic):
        """
        Factory method to get an instance of the correct Tactic to handle the
        given entity.
        """
        for candidate in next_config.tactics + DEFAULT_TACTICS:
            if candidate.trigger(entity, target, layer, next_config):
                tactic = candidate(entity, target, layer, next_config)
                if existing_tactic is not None:
                    tactic = tactic.combine(existing_tactic)
                return tactic
        raise BuildError('Unable to process file: {} '
                         '(no tactics matched)'.format(entity))

    def __init__(self, entity, target, layer, next_config):
        self.entity = entity
        self._layer = layer
        self._target = target
        self.data = None
        self._next_config = next_config

    def __call__(self):
        raise NotImplementedError

    def __str__(self):
        return "{}: {} -> {}".format(
            self.__class__.__name__, self.entity, self.target_file)

    @property
    def layer(self):
        """The file in the current layer under consideration"""
        return self._layer

    @property
    def target(self):
        """The target (final) layer."""
        return self._target

    @property
    def relpath(self):
        return self.entity.relpath(self.layer.directory)

    @property
    def target_file(self):
        target = self.target.directory / self.relpath
        return target

    @property
    def layer_name(self):
        return str(self.layer.directory.name)

    @property
    def repo_path(self):
        return path("/".join(self.layer.directory.splitall()[-2:]))

    @property
    def config(self):
        """
        Return the combined config from the layer above this (if any), this,
        and all lower layers.

        Note that it includes one layer higher so that the tactic can make
        decisions based on the upcoming layer.
        """
        return self._next_config

    def combine(self, existing):
        """Produce a tactic informed by the last tactic for an entry.
        This is when a rule in a higher level charm overrode something in
        one of its bases for example."""
        return self

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        """Should the rule trigger for a given path object"""
        return False

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        target = self.target_file
        sig = {}
        if target.exists() and target.isfile():
            sig[self.relpath] = (self.layer.url,
                                 self.kind,
                                 utils.sign(self.target_file))
        return sig

    def lint(self):
        return True

    def read(self):
        return None


class ExactMatch(object):
    FILENAME = None

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        relpath = entity.relpath(layer.directory)
        return cls.FILENAME == relpath


class IgnoreTactic(Tactic):
    """
    Tactic to handle per-layer ignores.

    If a given layer's ``layer.yaml`` has an ``ignore`` list, then any file
    or directory included in that list that is provided by base layers will
    be ignored, though any matching file or directory provided by the current
    or any higher level layers will be included.

    The ``ignore`` list uses the same format as a ``.gitignore`` file.
    """
    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        """
        Match if the given entity will be ignored by the next layer.
        """
        relpath = entity.relpath(layer.directory)
        ignored = utils.ignore_matcher(next_config.ignores)
        return not ignored(relpath)

    def __call__(cls):
        """
        If this tactic has not been replaced by another from a higher layer,
        then we want to drop the file entirely, so do nothing.
        """
        pass


class ExcludeTactic(Tactic):
    """
    Tactic to handle per-layer excludes.

    If a given layer's ``layer.yaml`` has an ``exclude`` list, then any file
    or directory included in that list that is provided by the current layer
    will be ignored, though any matching file or directory provided by base
    layers or any higher level layers will be included.

    The ``exclude`` list uses the same format as a ``.gitignore`` file.
    """
    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        """
        Match if the given entity is excluded by the current layer.
        """
        relpath = entity.relpath(layer.directory)
        excluded = utils.ignore_matcher(layer.config.excludes)
        return not excluded(relpath)

    def combine(self, existing):
        """
        Combine with the tactic for this file from the lower layer by
        returning the existing tactic, excluding any file or data from
        this layer.
        """
        return existing

    def __call__(self):
        """
        If no lower or higher level layer has provided a tactic for this file,
        then we want to just skip processing of this file, so do nothing.
        """
        pass


class CopyTactic(Tactic):
    def __call__(self):
        if self.entity.isdir():
            return
        target = self.target_file
        log.debug("Copying %s: %s", self.layer_name, target)
        # Ensure the path exists
        target.dirname().makedirs_p()
        if (self.entity != target) and not target.exists() \
                or not self.entity.samefile(target):
            data = self.read()
            if data:
                target.write_bytes(data)
                self.entity.copymode(target)
            else:
                self.entity.copy2(target)

    def __str__(self):
        return "Copy {}".format(self.entity)

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        return True


class InterfaceCopy(Tactic):
    def __init__(self, interface, relation_name, role, target, config):
        self.interface = interface
        self.relation_name = relation_name
        self.role = role
        self._target = target
        self._next_config = config

    @property
    def target(self):
        return self._target / "hooks/relations" / self.interface.name

    def __call__(self):
        # copy the entire tree into the
        # hooks/relations/<interface>
        # directory
        log.debug("Copying Interface %s: %s",
                  self.interface.name, self.target)
        ignorer = utils.ignore_matcher(self.config.ignores +
                                       self.interface.config.ignores)
        for entity, _ in utils.walk(self.interface.directory,
                                    lambda x: True,
                                    matcher=ignorer,
                                    kind="files"):
            target = entity.relpath(self.interface.directory)
            target = (self.target / target).normpath()
            target.parent.makedirs_p()
            entity.copy2(target)
        init = self.target / "__init__.py"
        if not init.exists():
            # ensure we can import from here directly
            init.touch()

    def __str__(self):
        return "Copy Interface {}".format(self.interface.name)

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        sigs = {}
        for entry, sig in utils.walk(self.target,
                                     utils.sign, kind="files"):
            relpath = entry.relpath(self._target.directory)
            sigs[relpath] = (self.interface.url, "static", sig)
        return sigs

    def lint(self):
        impl = self.interface.directory / self.role + '.py'
        if not impl.exists():
            log.error('Missing implementation for interface role: %s.py',
                      self.role)
            return False
        valid = True
        for entry in self.interface.directory.walkfiles():
            if entry.splitext()[1] != ".py":
                continue
            relpath = entry.relpath(self._target.directory)
            target = self._target.directory / relpath
            if not target.exists():
                continue
            unchanged = utils.delta_python_dump(entry, target,
                                                from_name=relpath)
            if not unchanged:
                valid = False
        return valid


class DynamicHookBind(Tactic):
    HOOKS = []

    def __init__(self, name, owner, target, config, template_file):
        self.name = name
        self.owner = owner
        self._target = target
        self._template_file = template_file
        self.targets = [self._target / "hooks" / hook.format(name)
                        for hook in self.HOOKS]

    def __call__(self):
        template = self._template_file.text()
        for target in self.targets:
            target.parent.makedirs_p()
            target.write_text(template.format(self.name))
            target.chmod(0o755)

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        sigs = {}
        for target in self.targets:
            rel = target.relpath(self._target.directory)
            sigs[rel] = (self.owner,
                         "dynamic",
                         utils.sign(target))
        return sigs

    def __str__(self):
        return "{}: {}".format(self.__class__.__name__, self.name)


class InterfaceBind(DynamicHookBind):
    HOOKS = [
        '{}-relation-joined',
        '{}-relation-changed',
        '{}-relation-broken',
        '{}-relation-departed'
    ]


class StorageBind(DynamicHookBind):
    HOOKS = [
        '{}-storage-attached',
        '{}-storage-detaching',
    ]


class ManifestTactic(ExactMatch, Tactic):
    FILENAME = ".composer.manifest"

    def __call__(self):
        # Don't copy manifests, they are regenerated
        pass


class SerializedTactic(ExactMatch, Tactic):
    kind = "dynamic"
    section = None
    prefix = None

    def __init__(self, *args, **kwargs):
        super(SerializedTactic, self).__init__(*args, **kwargs)
        self.data = {}
        self._read = False

    def load(self, fn):
        raise NotImplementedError('Must be implemented in subclass: load')

    def dump(self, data):
        raise NotImplementedError('Must be implemented in subclass: dump')

    def read(self):
        if not self._read:
            self.data = self.load(self.entity.open()) or {}
            self._read = True

    def combine(self, existing):
        # make sure both versions are read in
        existing.read()
        self.read()
        # merge them
        if existing.data and self.data:
            self.data = utils.deepmerge(existing.data, self.data)
        elif existing.data:
            self.data = dict(existing.data)
        return self

    def apply_edits(self):
        # Apply any editing rules from config
        config = self.config
        if config:
            section = config.get(self.section)
            if section:
                dels = section.get('deletes', [])
                if self.prefix:
                    namespace = self.data.get(self.prefix, {})
                else:
                    namespace = self.data
                for key in dels:
                    # TODO: Chuck edit this thing
                    utils.delete_path(key, namespace)
        if not self.target_file.parent.exists():
            self.target_file.parent.makedirs_p()

    def process(self):
        self.read()
        self.apply_edits()
        return self.data

    def __call__(self):
        self.dump(self.process())
        return self.data


class YAMLTactic(SerializedTactic):
    """Rule Driven YAML generation"""
    prefix = None

    def load(self, fn):
        """Load the yaml file and return the contents as objects."""
        try:
            return yaml.load(fn, Loader=yaml.RoundTripLoader)
        except yaml.YAMLError as e:
            log.debug(e)
            raise BuildError("Failed to process {0}. "
                             "Ensure the YAML is valid".format(fn.name))

    def dump(self, data):
        """Write the data to the target yaml file."""
        with open(self.target_file, 'w') as fd:
            yaml.dump(data, fd,
                      Dumper=yaml.RoundTripDumper,
                      default_flow_style=False,
                      default_style='"')


class JSONTactic(SerializedTactic):
    """Rule Driven JSON generation"""
    prefix = None

    def load(self, fn):
        return json.load(fn)

    def dump(self, data):
        json.dump(data, self.target_file.open('w'), indent=2)


class LayerYAML(YAMLTactic):
    """
    Process the ``layer.yaml`` file from each layer, and generate the
    resulting ``layer.yaml`` for the built charm.

    The input ``layer.yaml`` files can contain the following sections:

      * ``includes`` This is the heart of layering.  Layers and interface
        layers referenced in this list value are pulled in during charm
        build and combined with each other to produce the final layer.

      * ``config``, ``metadata``, ``dist``, or ``resources`` These objects can
        contain a ``deletes`` object to list keys that should be deleted from
        the resulting ``<section>.yaml``.

      * ``defines`` This object can contain a jsonschema used to defined and
        validate options passed to this layer from another layer.  The options
        and schema will be namespaced by the current layer name.  For example,
        layer "foo" defining ``bar: {type: string}`` will accept
        ``options: {foo: {bar: "foo"}}`` in the final ``layer.yaml``.

      * ``options`` This object can contain option name/value sections for
        other layers. For example, if the current layer includes the previously
        referenced "foo" layer, it could include ``foo: {bar: "foo"}`` in its
        ``options`` section.

    """
    FILENAMES = ["layer.yaml", "composer.yaml"]

    def __init__(self, *args, **kwargs):
        super(LayerYAML, self).__init__(*args, **kwargs)
        self.schema = {
            'type': 'object',
            'properties': {},
            'additionalProperties': False,
        }

    @property
    def target_file(self):
        # force the non-deprecated name
        return self.target.directory / "layer.yaml"

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        relpath = entity.relpath(layer.directory)
        return relpath in cls.FILENAMES

    def read(self):
        if not self._read:
            super(LayerYAML, self).read()
            ignores = self.data.get('ignore')
            if isinstance(ignores, list):
                self.data['ignore'] = {
                    self.layer_name: ignores,
                }
            self.data.setdefault('options', {})
            self.schema['properties'] = {
                self.layer_name: {
                    'type': 'object',
                    'properties': self.data.pop('defines', {}),
                    'default': {},
                },
            }

    def combine(self, existing):
        self.read()
        existing.read()
        super(LayerYAML, self).combine(existing)
        self.schema = utils.deepmerge(existing.schema, self.schema)
        return self

    def lint(self):
        self.read()
        defined_layer_names = set(self.schema['properties'].keys())
        options_layer_names = set(self.data['options'].keys())
        unknown_layer_names = options_layer_names - defined_layer_names
        if unknown_layer_names:
            log.error('Options set for undefined layer{s}: {layers}'.format(
                s='s' if len(unknown_layer_names) > 1 else '',
                layers=', '.join(unknown_layer_names)))
            return False
        validator = extend_with_default(
            jsonschema.Draft4Validator)(self.schema)
        valid = True
        for error in validator.iter_errors(self.data['options']):
            log.error('Invalid value for option %s: %s',
                      '.'.join(error.absolute_path), error.message)
            valid = False
        return valid

    def __call__(self):
        # rewrite includes to be the current source
        data = self.data
        if data is None:
            return
        # The split should result in the series/charm path only
        # XXX: there will be strange interactions with cs: vs local:
        if 'is' not in data:
            data['is'] = str(self.layer.url)
        inc = data.get('includes', [])
        norm = []
        for i in inc:
            if ":" in i:
                norm.append(i)
            else:
                # Attempt to normalize to a repository base
                norm.append("/".join(path(i).splitall()[-2:]))
        if norm:
            data['includes'] = norm
        if not self.target_file.parent.exists():
            self.target_file.parent.makedirs_p()
        self.dump(data)
        return data

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        target = self.target_file
        sig = {}
        if target.exists() and target.isfile():
            sig["layer.yaml"] = (self.layer.url,
                                 self.kind,
                                 utils.sign(self.target_file))
        return sig


class MetadataYAML(YAMLTactic):
    """Rule Driven metadata.yaml generation"""
    section = "metadata"
    FILENAME = "metadata.yaml"
    KEY_ORDER = [
        "name",
        "summary",
        "maintainer",
        "maintainers",
        "description",
        "tags",
        "requires",
        "provides",
        "peers",
    ]

    def __init__(self, *args, **kwargs):
        super(MetadataYAML, self).__init__(*args, **kwargs)
        self.storage = {}
        self.maintainer = None
        self.maintainers = []

    def read(self):
        if not self._read:
            super(MetadataYAML, self).read()
            self.storage = {name: self.layer.url
                            for name in self.data.get('storage', {}).keys()}
            self.maintainer = self.data.get('maintainer')
            self.maintainers = self.data.get('maintainers')

    def combine(self, existing):
        super(MetadataYAML, self).combine(existing)
        self.storage.update(existing.storage)
        return self

    def apply_edits(self):
        super(MetadataYAML, self).apply_edits()
        # Remove the merged maintainers from the self.data
        self.data.pop('maintainer', None)
        self.data.pop('maintainers', [])
        # Set the maintainer and maintainers only from this layer.
        if self.maintainer:
            self.data['maintainer'] = self.maintainer
        if self.maintainers:
            self.data['maintainers'] = self.maintainers
        if not self.config or not self.config.get(self.section):
            return
        for key in self.config[self.section].get('deletes', []):
            if not key.startswith('storage.'):
                continue
            _, name = key.split('.', 1)
            if '.' in name:
                continue
            self.storage.pop(name, None)

    def dump(self, data):
        final = yaml.comments.CommentedMap()
        # attempt keys in the desired order
        for k in self.KEY_ORDER:
            if k in data:
                final[k] = data[k]
        # Get the remaining keys that are unordered.
        remaining = set(data.keys()) - set(self.KEY_ORDER)
        for k in sorted(remaining):
            final[k] = data[k]
        super(MetadataYAML, self).dump(final)


class ConfigYAML(YAMLTactic):
    """Rule driven config.yaml generation"""
    section = "config"
    prefix = "options"
    FILENAME = "config.yaml"


class ActionsYAML(YAMLTactic):
    """Rule driven actions.yaml generation"""
    section = "actions"
    FILENAME = "actions.yaml"


class DistYAML(YAMLTactic):
    """Rule driven dist.yaml generation"""
    section = "dist"
    prefix = None
    FILENAME = "dist.yaml"


class ResourcesYAML(YAMLTactic):
    """Rule driven resources.yaml generation"""
    section = "resources"
    prefix = None
    FILENAME = "resources.yaml"


class InstallerTactic(Tactic):
    def __str__(self):
        return "Installing software to {}".format(self.relpath)

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        relpath = entity.relpath(layer.directory)
        ext = relpath.splitext()[1]
        return ext in [".pypi", ]

    def __call__(self):
        # install package reference in trigger file
        # in place directory of target
        # XXX: Should this map multiline to "-r", self.entity
        spec = self.entity.text().strip()
        target = self.target_file.dirname()
        log.debug("pip installing {} as {}".format(
            spec, target))
        with utils.tempdir(chdir=False) as temp_dir:
            # We do this dance so we don't have
            # to guess package and .egg file names
            # we move everything in the tempdir to the target
            # and track it for later use in sign()
            localenv = os.environ.copy()
            localenv['PYTHONUSERBASE'] = temp_dir
            utils.Process(("pip3",
                           "install",
                           "--user",
                           "--ignore-installed",
                           spec), env=localenv).exit_on_error()()
            self._tracked = []
            # We now manage two classes of explicit mappings
            # When python packages are installed into a prefix
            # we know that bin/* should map to <charmdir>/bin/
            # and lib/python*/site-packages/* should map to
            # <target>/*
            src_paths = ["bin/*", "lib/python*/site-packages/*"]
            for p in src_paths:
                for d in temp_dir.glob(p):
                    if not d.exists():
                        continue
                    bp = d.relpath(temp_dir)
                    if bp.startswith("bin/"):
                        dst = self.target / bp
                    elif bp.startswith("lib"):
                        dst = target / d.name
                    else:
                        dst = target / bp
                    if dst.exists():
                        if dst.isdir():
                            dst.rmtree_p()
                        elif dst.isfile():
                            dst.remove()
                    if not dst.parent.exists():
                        dst.parent.makedirs_p()
                    log.debug("Installer moving {} to {}".format(d, dst))
                    d.move(dst)
                    self._tracked.append(dst)

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        sigs = {}
        for d in self._tracked:
            if d.isdir():
                for entry, sig in utils.walk(d,
                                             utils.sign, kind="files"):
                    relpath = entry.relpath(self.target.directory)
                    sigs[relpath] = (self.layer.url, "dynamic", sig)
            elif d.isfile():
                relpath = d.relpath(self.target.directory)
                sigs[relpath] = (
                    self.layer.url, "dynamic", utils.sign(d))
        return sigs


class WheelhouseTactic(ExactMatch, Tactic):
    kind = "dynamic"
    FILENAME = 'wheelhouse.txt'

    def __init__(self, *args, **kwargs):
        super(WheelhouseTactic, self).__init__(*args, **kwargs)
        self.tracked = []
        self.previous = []

    def __str__(self):
        directory = self.target.directory / 'wheelhouse'
        return "Building wheelhouse in {}".format(directory)

    def combine(self, existing):
        self.previous = existing.previous + [existing]
        return self

    def _add(self, pip, wheelhouse, *reqs):
        with utils.tempdir(chdir=False) as temp_dir:
            # put in a temp dir first to ensure we track all of the files
            utils.Process((pip, 'install',
                           '--no-binary', ':all:',
                           '-d', temp_dir) +
                          reqs).exit_on_error()()
            for wheel in temp_dir.files():
                dest = wheelhouse / wheel.basename()
                dest.remove_p()
                wheel.move(wheelhouse)
                self.tracked.append(dest)

    def __call__(self, venv=None):
        create_venv = venv is None
        venv = venv or path(tempfile.mkdtemp())
        pip = venv / 'bin' / 'pip3'
        wheelhouse = self.target.directory / 'wheelhouse'
        wheelhouse.mkdir_p()
        if create_venv:
            utils.Process(
                ('virtualenv', '--python', 'python3', venv)).exit_on_error()()
            utils.Process(
                (pip, 'install', '-U', 'pip', 'wheel')).exit_on_error()()
        for tactic in self.previous:
            tactic(venv)
        self._add(pip, wheelhouse, '-r', self.entity)
        if create_venv:
            venv.rmtree_p()

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        sigs = {}
        for tactic in self.previous:
            sigs.update(tactic.sign())
        for d in self.tracked:
            relpath = d.relpath(self.target.directory)
            sigs[relpath] = (
                self.layer.url, "dynamic", utils.sign(d))
        return sigs


def load_tactic(dpath, basedir):
    """Load a tactic from the current layer using a dotted path. The last
    element in the path should be a Tactic subclass
    """
    obj = utils.load_class(dpath, basedir)
    if not issubclass(obj, Tactic):
        raise ValueError("Expected to load a tactic for %s" % dpath)
    return obj


def extend_with_default(validator_class):
    """
    Extend a jsonschema validator to propagate default values prior
    to validating.
    """
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.iteritems():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        for error in validate_properties(
                validator, properties, instance, schema):
            yield error

    return jsonschema.validators.extend(
        validator_class, {"properties": set_defaults},
    )


DEFAULT_TACTICS = [
    IgnoreTactic,
    ExcludeTactic,
    ManifestTactic,
    WheelhouseTactic,
    InstallerTactic,
    DistYAML,
    ResourcesYAML,
    MetadataYAML,
    ConfigYAML,
    ActionsYAML,
    LayerYAML,
    CopyTactic
]
