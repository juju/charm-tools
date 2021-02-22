from inspect import getargspec
import errno
import json
import logging
import os
import tarfile
import tempfile
import zipfile

import jsonschema

import requirements
from path import Path as path
from pkg_resources import safe_name
from ruamel import yaml
from charmtools import utils
from charmtools import fetchers
from charmtools.build.errors import BuildError

log = logging.getLogger(__name__)


if not hasattr(yaml, 'danger_load'):
    # follow convention for pyyaml 4.1
    yaml.danger_load = yaml.load


class Tactic(object):
    """
    Base class for all tactics.

    Subclasses must implement at least ``trigger`` and ``process``, and
    probably also want to implement ``combine``.
    """
    kind = "static"  # used in signatures
    _warnings = {}  # deprecation warnings we've shown

    @classmethod
    def get(cls, entity, target, layer, next_config, current_config,
            existing_tactic):
        """
        Factory method to get an instance of the correct Tactic to handle the
        given entity.
        """
        for candidate in current_config.tactics + DEFAULT_TACTICS:
            argspec = getargspec(candidate.trigger)
            if len(argspec.args) == 2:
                # old calling convention
                name = candidate.__name__
                if name not in Tactic._warnings:
                    Tactic._warnings[name] = True
                    log.warn(
                        'Deprecated method signature for trigger in %s', name)
                args = [entity.relpath(layer.directory)]
            else:
                # new calling convention
                args = [entity, target, layer, next_config]
            if candidate.trigger(*args):
                tactic = candidate(entity, target, layer, next_config)
                if existing_tactic is not None:
                    tactic = tactic.combine(existing_tactic)
                return tactic
        raise BuildError('Unable to process file: {} '
                         '(no tactics matched)'.format(entity))

    def __init__(self, entity, target, layer, next_config):
        self._entity = entity
        self._layer = layer
        self._target = target
        self.data = None
        self._next_config = next_config

    def process(self):
        """
        Now that the tactics for the current entity have been combined for
        all layers, process the entity to produce the final output file.

        Must be implemented by a subclass.
        """
        raise NotImplementedError

    def __call__(self):
        return self.process()

    def __str__(self):
        return "{}: {} -> {}".format(
            self.__class__.__name__, self.entity, self.target_file)

    @property
    def entity(self):
        """
        The current entity (a.k.a. file) being processed.
        """
        return self._entity

    @property
    def layer(self):
        """The current layer under consideration"""
        return self._layer

    @property
    def current(self):
        """Alias for ``Tactic.layer``"""
        return self.layer

    @property
    def target(self):
        """The target (final) layer."""
        return self._target

    @property
    def relpath(self):
        """
        The path to the file relative to the layer.
        """
        return self.entity.relpath(self.layer.directory)

    @property
    def target_file(self):
        """
        The location where the processed file will be written to.
        """
        target = self.target.directory / self.relpath
        return target

    @property
    def layer_name(self):
        """
        Name of the current layer being processed.
        """
        return self.layer.name

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
        """
        Produce a tactic informed by the existing tactic for an entry.

        This is when a rule in a higher level charm overrode something in
        one of its bases for example.

        Should be implemented by a subclass if any sort of merging behavior is
        desired.
        """
        return self

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        """
        Determine whether the rule should apply to a given entity (file).

        Generally, this should check the entity name, but could conceivably
        also inspect the contents of the file.

        Must be implemented by a subclass or the tactic will never match.
        """
        return False

    def sign(self):
        """
        Return signature in the form ``{relpath: (origin layer, SHA256)}``

        Can be overridden by a subclass, but the default implementation will
        usually be fine.
        """
        target = self.target_file
        sig = {}
        if target.exists() and target.isfile():
            sig[self.relpath] = (self.layer.url,
                                 self.kind,
                                 utils.sign(self.target_file))
        return sig

    def lint(self):
        """
        Test the resulting file to ensure that it is valid.

        Return ``True`` if valid.  If invalid, return ``False`` or raise a
        :class:`~charmtools.build.errors.BuildError`

        Should be implemented by a subclass.
        """
        return True

    def read(self):
        """
        Read the contents of the file to be processed.

        Can be implemented by a subclass.  By default, returns ``None``.
        """
        return None


class ExactMatch(object):
    """
    Mixin to match a file with an exact name.
    """
    FILENAME = None
    "The filename to be matched"

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        """
        Match if the current entity's filename is what we're looking for.
        """
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
        ""  # suppress inherited doc
        # Match if the given entity will be ignored by the next layer.
        relpath = entity.relpath(layer.directory)
        ignored = utils.ignore_matcher(next_config.ignores)
        return not ignored(relpath)

    def __call__(cls):
        # If this tactic has not been replaced by another from a higher layer,
        # then we want to drop the file entirely, so do nothing.
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
        ""  # suppress inherited doc
        # Match if the given entity is excluded by the current layer.
        relpath = entity.relpath(layer.directory)
        excluded = utils.ignore_matcher(layer.config.excludes)
        return not excluded(relpath)

    def combine(self, existing):
        ""  # suppress inherited doc
        # Combine with the tactic for this file from the lower layer by
        # returning the existing tactic, excluding any file or data from
        # this layer.
        return existing

    def __call__(self):
        # If no lower or higher level layer has provided a tactic for this
        # file, then we want to just skip processing of this file, so do
        # nothing.
        pass


class CopyTactic(Tactic):
    """
    Tactic to copy a file without modification or merging.

    The last version of the file "wins" (e.g., from the charm layer).

    This is the final fallback tactic if nothing else matches.
    """
    def __call__(self):
        if self.entity.isdir():
            log.debug('Creating %s', self.target_file)
            return self.target_file.makedirs_p()
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
        ""  # suppress inherited doc
        # Always matches.
        return True


class InterfaceCopy(Tactic):
    """
    Tactic to process a relation endpoint using an interface layer.

    This tactic is not part of the normal set of tactics that are matched
    against files.  Instead, it is manually called for each relation endpoint
    that has a corresponding interface layer.
    """
    def __init__(self, interface, relation_name, role, target, config):
        self.interface = interface
        self.relation_name = relation_name
        self.role = role
        self._target = target
        self._next_config = config

    @property
    def target(self):
        ""  # suppress inherited doc
        return (path(self._target.directory) /
                "hooks/relations" /
                self.interface.name)

    def __call__(self):
        # copy the entire tree into the
        # hooks/relations/<interface>
        # directory
        log.debug("Copying Interface %s: %s",
                  self.interface.name, self.target)
        ignorer = utils.ignore_matcher(self.config.ignores +
                                       self.interface.config.ignores +
                                       self.config.excludes +
                                       self.interface.config.excludes)
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
        ""  # suppress inherited doc
        # Sign all of the files that were put into place.
        sigs = {}
        for entry, sig in utils.walk(self.target,
                                     utils.sign, kind="files"):
            relpath = entry.relpath(self._target.directory)
            sigs[relpath] = (self.interface.url, "static", sig)
        return sigs

    def lint(self):
        ""  # suppress inherited doc
        # Ensure that the interface layer used is valid.
        impl = self.interface.directory / self.role + '.py'
        if not impl.exists():
            log.error('Missing implementation for interface role: %s.py',
                      self.role)
            return False
        valid = True
        ignorer = utils.ignore_matcher(self.config.ignores +
                                       self.interface.config.ignores +
                                       self.config.excludes +
                                       self.interface.config.excludes)
        for entry, _ in utils.walk(self.interface.directory,
                                   lambda x: True,
                                   matcher=ignorer,
                                   kind="files"):
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
    """
    Base class for process hooks dynamically generated from the hook template.

    This tactic is not used directly, but serves as a base for the
    type-specific dynamic hook tactics, like
    :class:`~charmtools.build.tactics.StandardHooksBind`, or
    :class:`~charmtools.build.tactics.InterfaceBind`.
    """
    HOOKS = []
    """
    List of all hooks to populate.
    """

    def __init__(self, name, owner, target, config, output_files,
                 template_file):
        """
        Initialize an instance of this tactic (should be a subclass of
        `DynamicHookBind`).

        :param name: Name of the category for this type of hook.  E.g.,
            could be the name of a relation, for relation hooks, the name
            of a storage endpoint, for storage hooks, 'hook' for standard
            hooks, etc.
        :type name: str
        :param owner: URL of layer that owns the target.
        :type owner: str
        :param target: Layer representing the build target.
        :type target: Layer
        :param config: Config for layer being built
        :type config: BuildConfig
        :param output_files: Mapping of file Paths to Tactics that should
            should process that file.
        :type output_files: dict
        :param template_file: Path to the template to render into hooks.
        :type template_file: path.Path
        """
        self.name = name
        self.owner = owner
        self._target = target
        self._config = config
        self._output_files = output_files
        self._template_file = template_file
        self.targets = [
            path(self._target.directory) / "hooks" / hook.format(name)
            for hook in self.HOOKS]
        self.tracked = []

    def __call__(self):
        """
        Copy the template file into place for all the files listed in
        ``HOOKS``.

        If a given hook already has an implementation provided, it will take
        precedence over the template.

        The template is generally located at ``hooks/hook.template``
        """
        template = self._template_file.text()
        for target in self.targets:
            if target.relpath(self._target.directory) in self._output_files:
                continue
            target.parent.makedirs_p()
            target.write_text(template.format(self.name))
            target.chmod(0o755)
            self.tracked.append(target)

    def sign(self):
        """
        Sign all hook files generated by this tactic.
        """
        sigs = {}
        for target in self.tracked:
            rel = target.relpath(self._target.directory)
            sigs[rel] = (self.owner,
                         "dynamic",
                         utils.sign(target))
        return sigs

    def __str__(self):
        return "{}: {}".format(self.__class__.__name__, self.name)


class StandardHooksBind(DynamicHookBind):
    """
    Tactic to copy the hook template into place for all standard hooks.

    This tactic is not part of the normal set of tactics that are matched
    against files.  Instead, it is manually called to fill in the standard
    set of hook implementations.
    """
    HOOKS = [
        'install',
        'config-changed',
        'leader-elected',
        'leader-settings-changed',
        'start',
        'stop',
        'update-status',
        'upgrade-charm',
        'pre-series-upgrade',
        'post-series-upgrade',
    ]


class InterfaceBind(DynamicHookBind):
    """
    Tactic to copy the hook template into place for all relation hooks.

    This tactic is not part of the normal set of tactics that are matched
    against files.  Instead, it is manually called to fill in the set of
    relation hooks needed by this charm.
    """
    HOOKS = [
        '{}-relation-created',
        '{}-relation-joined',
        '{}-relation-changed',
        '{}-relation-broken',
        '{}-relation-departed'
    ]


class StorageBind(DynamicHookBind):
    """
    Tactic to copy the hook template into place for all storage hooks.

    This tactic is not part of the normal set of tactics that are matched
    against files.  Instead, it is manually called to fill in the set of
    storage hooks needed by this charm.
    """
    HOOKS = [
        '{}-storage-attached',
        '{}-storage-detaching',
    ]


class ManifestTactic(ExactMatch, Tactic):
    """
    Tactic to avoid copying a build manifest file from a base layer.
    """
    FILENAME = ".build.manifest"

    def __call__(self):
        # Don't copy manifests, they are regenerated
        pass


class SerializedTactic(ExactMatch, Tactic):
    """
    Base class for tactics which deal with serialized data, such as YAML or
    JSON.
    """
    kind = "dynamic"
    section = None
    prefix = None

    def __init__(self, *args, **kwargs):
        super(SerializedTactic, self).__init__(*args, **kwargs)
        self.data = {}
        self._read = False

    def load(self, fn):
        """
        Load and deserialize the data from the file.

        Must be impelemented by a subclass.
        """
        raise NotImplementedError('Must be implemented in subclass: load')

    def dump(self, data):
        """
        Serialize and write the data to the file.

        Must be impelemented by a subclass.
        """
        raise NotImplementedError('Must be implemented in subclass: dump')

    def read(self):
        """
        Read and cache the data into memory, using ``self.load()``.
        """
        if not self._read:
            self.data = self.load(self.entity.open()) or {}
            self._read = True

    def combine(self, existing):
        """
        Merge the deserialized data from two layers using ``deepmerge``.
        """
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
        """
        Apply any edits defined in the final ``layer.yaml`` file to the data.

        An example edit definition:

        .. code-block:: yaml

           metadata:
             deletes:
               - requires.http
        """
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
        """
        Load, process, and write the file.
        """
        self.dump(self.process())
        return self.data


class YAMLTactic(SerializedTactic):
    """
    Base class for tactics dealing with YAML data.

    Tries to ensure that the order of keys is preserved.
    """
    prefix = None

    def load(self, fn):
        try:
            return yaml.danger_load(fn, Loader=yaml.RoundTripLoader)
        except yaml.YAMLError as e:
            log.debug(e)
            raise BuildError("Failed to process {0}. "
                             "Ensure the YAML is valid".format(fn.name))

    def dump(self, data):
        with open(self.target_file, 'w') as fd:
            yaml.dump(data, fd,
                      Dumper=yaml.RoundTripDumper,
                      default_flow_style=False,
                      default_style='"')


class JSONTactic(SerializedTactic):
    """
    Base class for tactics dealing with JSON data.
    """
    prefix = None

    def load(self, fn):
        return json.load(fn)

    def dump(self, data):
        json.dump(data, self.target_file.open('w'), indent=2)


class LayerYAML(YAMLTactic):
    """
    Tactic for processing and combining the ``layer.yaml`` file from
    each layer.

    The input ``layer.yaml`` files can contain the following sections:

      * ``includes`` This is the heart of layering.  Layers and interface
        layers referenced in this list value are pulled in during charm
        build and combined with each other to produce the final layer.

      * ``defines`` This object can contain a jsonschema used to define and
        validate options passed to this layer from another layer.  The options
        and schema will be namespaced by the current layer name.

      * ``options`` This object can contain option name/value sections for
        other layers.

      * ``config``, ``metadata``, ``dist``, or ``resources`` These objects can
        contain a ``deletes`` object to list keys that should be deleted from
        the resulting ``<section>.yaml``.

    Example, layer ``foo`` might define this ``layer.yaml`` file:

    .. code-block:: yaml

        includes:
          - layer:basic
          - interface:foo
        defines:
          foo-opt:
            type: string
            default: 'foo-default'
        options:
          basic:
            use_venv: true

    And layer ``bar`` might define this ``layer.yaml`` file:

    .. code-block:: yaml

        includes:
          - layer:foo
        options:
          foo-opt: 'bar-value'
        metadata:
          deletes:
            - 'requires.foo-relation'
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
        ""  # suppress inherited doc
        # force the non-deprecated name
        return self.target.directory / "layer.yaml"

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        ""  # suppress inherited doc
        relpath = entity.relpath(layer.directory)
        return relpath in cls.FILENAMES

    def read(self):
        ""  # suppress inherited doc
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
        ""  # suppress inherited doc
        self.read()
        existing.read()
        super(LayerYAML, self).combine(existing)
        self.schema = utils.deepmerge(existing.schema, self.schema)
        return self

    def lint(self):
        ""  # suppress inherited doc
        self.read()
        defined_layer_names = set(self.schema['properties'].keys())
        options_layer_names = set(self.data['options'].keys())
        unknown_layer_names = options_layer_names - defined_layer_names
        unknown_layer_names -= {'charms.reactive'}
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
        inc = data.get('includes', []) or []
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
        ""  # suppress inherited doc
        target = self.target_file
        sig = {}
        if target.exists() and target.isfile():
            sig["layer.yaml"] = (self.layer.url,
                                 self.kind,
                                 utils.sign(self.target_file))
        return sig


class MetadataYAML(YAMLTactic):
    """
    Tactic for processing and combining the ``metadata.yaml`` file from
    each layer.
    """
    section = "metadata"
    FILENAME = "metadata.yaml"
    KEY_ORDER = [
        "name",
        "summary",
        "maintainer",
        "maintainers",
        "description",
        "tags",
        "series",
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
        ""  # suppress inherited doc
        if not self._read:
            super(MetadataYAML, self).read()
            self.storage = {name: self.layer.url
                            for name in self.data.get('storage', {}).keys()}
            self.maintainer = self.data.get('maintainer')
            self.maintainers = self.data.get('maintainers')

    def combine(self, existing):
        ""  # suppress inherited doc
        self.read()
        series = self.data.get('series', [])
        super(MetadataYAML, self).combine(existing)
        if series:
            self.data['series'] = series + existing.data.get('series', [])
        self.storage.update(existing.storage)
        return self

    def apply_edits(self):
        ""  # suppress inherited doc
        super(MetadataYAML, self).apply_edits()
        # Remove the merged maintainers from the self.data
        self.data.pop('maintainer', None)
        self.data.pop('maintainers', [])
        # Set the maintainer and maintainers only from this layer.
        if self.maintainer:
            self.data['maintainer'] = self.maintainer
        if self.maintainers:
            self.data['maintainers'] = self.maintainers
        if 'series' in self.data:
            self.data['series'] = list(utils.OrderedSet(self.data['series']))
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
        ""  # suppress inherited doc
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
    """
    Tactic for processing and combining the ``config.yaml`` file from
    each layer.
    """
    section = "config"
    prefix = "options"
    FILENAME = "config.yaml"


class ActionsYAML(YAMLTactic):
    """
    Tactic for processing and combining the ``actions.yaml`` file from
    each layer.
    """
    section = "actions"
    FILENAME = "actions.yaml"


class DistYAML(YAMLTactic):
    """
    Tactic for processing and combining the ``dist.yaml`` file from
    each layer.
    """
    section = "dist"
    prefix = None
    FILENAME = "dist.yaml"


class ResourcesYAML(YAMLTactic):
    """
    Tactic for processing and combining the ``resources.yaml`` file from
    each layer.
    """
    section = "resources"
    prefix = None
    FILENAME = "resources.yaml"


class InstallerTactic(Tactic):
    """
    Tactic to process any ``.pypi`` files and install Python packages directly
    into the charm's ``lib/`` directory.

    This is used in Kubernetes type charms due to the lack of a proper install
    or bootstrap phase.
    """
    def __str__(self):
        return "Installing software to {}".format(self.relpath)

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        ""  # suppress inherited doc
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
        ""  # suppress inherited doc
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
    """
    Tactic to process the ``wheelhouse.txt`` file and build a source-only
    wheelhouse of Python packages in the charm's ``wheelhouse/`` directory.
    """
    kind = "dynamic"
    FILENAME = 'wheelhouse.txt'
    removed = []  # has to be class level to affect all tactics during signing
    per_layer = False

    def __init__(self, *args, **kwargs):
        super(WheelhouseTactic, self).__init__(*args, **kwargs)
        self.tracked = []
        self.previous = []
        self.lines = None
        self._venv = None
        self.purge_wheels = False
        self._layer_refs = {}
        self.modules = {}
        self.lock_info = []

    def __str__(self):
        directory = self.target.directory / 'wheelhouse'
        return "Building wheelhouse in {}".format(directory)

    def combine(self, existing):
        ""  # suppress inherited doc
        self.previous = existing.previous + [existing]
        existing.read()
        self._layer_refs.update(existing._layer_refs)
        self.read()
        new_pkgs = set()
        for line in self.lines:
            try:
                req = next(requirements.parse(line))
                new_pkgs.add(safe_name(req.name))
                self.modules[req.name] = req
            except (StopIteration, ValueError):
                pass  # ignore comments, blank lines, etc
        existing_lines = []
        for line in existing.lines:
            try:
                req = next(requirements.parse(line))
                # new explicit reqs will override existing ones
                if safe_name(req.name) not in new_pkgs:
                    existing_lines.append(line)
                    self.modules[req.name] = req
                else:
                    existing_lines.append('# {}  # overridden by {}'
                                          .format(line, self.layer.url))
            except (StopIteration, ValueError):
                existing_lines.append(line)  # ignore comments, blank lines, &c
        self.lines = existing_lines + self.lines
        return self

    def read(self):
        if self.lines is None:
            src = path(self.entity)
            if src.exists():
                for req in requirements.parse(src.text()):
                    if req.name is None:
                        raise BuildError(
                            'Unable to determine package name for "{}"; '
                            'did you forget "#egg=..."?'
                            .format(req.line.strip()))
                    self._layer_refs[safe_name(req.name)] = self.layer.url
                self.lines = (['# ' + self.layer.url] +
                              src.lines(retain=False) +
                              [''])
            else:
                self.lines = []

    def _add(self, wheelhouse, *reqs):
        with utils.tempdir(chdir=False) as temp_dir:
            # put in a temp dir first to ensure we track all of the files
            self._pip('download', '--no-binary', ':all:', '-d', temp_dir,
                      *reqs)
            log.debug('Copying wheels:')
            for wheel in temp_dir.files():
                log.debug('  ' + wheel.name)
                dest = wheelhouse / wheel.basename()
                if dest in self.tracked:
                    return
                if self.purge_wheels:
                    unversioned_wheel = wheel.basename().split('-')[0]
                    for old_wheel in wheelhouse.glob(unversioned_wheel + '-*'):
                        old_wheel.remove()
                        if old_wheel != dest:
                            self.removed.append(old_wheel)
                else:
                    dest.remove_p()
                # extract the version from the wheelhouse name
                name = None
                if wheel.name.endswith(".zip"):
                    name = wheel.name[:-4]
                elif wheel.name.endswith(".tar.gz"):
                    name = wheel.name[:-7]
                if name is not None:
                    ns = name.split('-')
                    version = ns[-1]
                    package = '-'.join(ns[:-1])
                    log.debug("Version extracted is: %s version %s",
                              package, version)
                    # we also need to determine if it was a git repo and
                    # extract the branch/commit
                    if package in self.modules:
                        req = self.modules[package]
                        log.debug("module: %s - is vcs: %s", package, req.vcs)
                        if req.vcs:
                            (branch, version) = self._extract_pkg_vcs(wheel,
                                                                      req)
                            log.debug("branch: %s, version=%s",
                                      branch, version)
                            self.lock_info.append({
                                "type": "python_module",
                                "package": package,
                                "url": req.uri,
                                "branch": branch,
                                "version": version,
                                "vcs": req.vcs
                            })
                        else:
                            # keep the python module and version we build
                            log.debug("not a vcs, therefore %s==%s",
                                      package, version)
                            self.lock_info.append({
                                "type": "python_module",
                                "package": package,
                                "vcs": None,
                                "version": version,
                            })
                    else:
                        # keep the python module and version we build
                        log.debug("Just keeping %s==%s", package, version)
                        self.lock_info.append({
                            "type": "python_module",
                            "package": package,
                            "vcs": None,
                            "version": version,
                        })
                wheel.move(wheelhouse)
                self.tracked.append(dest)

    @staticmethod
    def _extract_pkg_vcs(wheel, req):
        with utils.tempdir(chdir=False) as temp_dir:
            dst_file = temp_dir / wheel.name
            dst_dir = temp_dir / 'unarchive'
            wheel.copy(dst_file)
            if dst_file.endswith('.zip'):
                with zipfile.ZipFile(dst_file, 'r') as zip_ref:
                    zip_ref.extractall(dst_dir)
            elif dst_file.endswith('.tar.gz'):
                with tarfile.open(dst_file, 'r') as archive:
                    archive.extractall(path=dst_dir)
            else:
                raise RuntimeError("Can only handle zips or tar.gz?")
            # now use Fetcher to extract the branch and revision
            vcs_dir = dst_dir / req.name
            fetcher = fetchers.Fetcher(vcs_dir)
            revision = fetcher.get_revision(vcs_dir)
            branch = fetcher.get_branch_for_revision(vcs_dir, revision)
            return (branch, revision)

    def _run_in_venv(self, *args):
        assert self._venv is not None
        # have to use bash to activate the venv properly first
        res = utils.Process(('bash', '-c', ' '.join(
            ('.', self._venv / 'bin' / 'activate', ';') + args
        )))()
        if res.exit_code != 0:
            raise BuildError(res.output)
        return res

    def _pip(self, *args):
        return self._run_in_venv('pip3', *args)

    def __call__(self):
        create_venv = self._venv is None
        self._venv = self._venv or path(tempfile.mkdtemp())
        wheelhouse = self.target.directory / 'wheelhouse'
        wheelhouse.mkdir_p()
        if create_venv:
            utils.Process(
                ('virtualenv', '--python', 'python3', self._venv)
            ).exit_on_error()()
        if self.per_layer:
            self._process_per_layer(wheelhouse)
        else:
            self._process_combined(wheelhouse)
        # clean up
        if create_venv:
            self._venv.rmtree_p()
            self._venv = None

    def _process_per_layer(self, wheelhouse):
        # we are the top layer; process all lower layers first
        for tactic in self.previous:
            tactic()
        # process this layer
        log.debug('Processing wheelhouse for {}'.format(self.layer.url))
        self._add(wheelhouse, '-r', self.entity)

    def _process_combined(self, wheelhouse):
        log.debug('Processing wheelhouse:')
        self.read()
        for line in self.lines:
            log.debug('  ' + line.strip())
        with utils.tempdir(chdir=False) as temp_dir:
            wh_file = temp_dir / 'wheelhouse.txt'
            wh_file.write_lines(self.lines)
            self._add(wheelhouse, '-r', wh_file)
            wh_file.move(self.target.directory / 'wheelhouse.txt')

    def sign(self):
        ""  # suppress inherited doc
        sigs = {}
        if self.per_layer:
            for tactic in self.previous:
                sigs.update(tactic.sign())
        else:
            sigs['wheelhouse.txt'] = (
                self.layer.url,
                "dynamic",
                utils.sign(self.target.directory / 'wheelhouse.txt'),
            )
        for d in self.tracked:
            if d in self.removed:
                continue
            relpath = d.relpath(self.target.directory)
            pkg_name = safe_name(d.basename().split('-')[0])
            layer_url = self._layer_refs.get(pkg_name, '__pip__')
            sigs[relpath] = (
                layer_url, "dynamic", utils.sign(d))
        return sigs


class CopyrightTactic(Tactic):
    """
    Tactic to combine the copyright info from all layers into a final
    machine-readable format.
    """
    def __init__(self, *args, **kwargs):
        super(CopyrightTactic, self).__init__(*args, **kwargs)
        self.previous = []
        self.toplevel = True
        self.relpath_target = self.relpath

    def combine(self, existing):
        ""  # suppress inherited doc
        self.previous = existing.previous + [existing]
        existing.previous = []
        existing.toplevel = False
        existing.relpath_target += ".{}-{}".format(
            existing.layer.NAMESPACE,
            existing.layer.name)
        return self

    @property
    def target_file(self):
        ""  # suppress inherited doc
        target = self.target.directory / self.relpath_target
        return target

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        ""  # suppress inherited doc
        relpath = entity.relpath(layer.directory)
        return relpath == "copyright"

    def __call__(self):
        # Process the `copyright` file for all levels below us.
        for tactic in self.previous:
            tactic()
        self.target_file.dirname().makedirs_p()
        # Only copy file if it changed
        if not self.target_file.exists()\
                or not self.entity.samefile(self.target_file):
            data = self.read()
            if data:
                self.target_file.write_bytes(data)
                self.entity.copymode(self.target_file)
            else:
                self.entity.copy2(self.target_file)

    def sign(self):
        ""  # suppress inherited doc
        sigs = {}
        # sign the `copyright` file for all levels below us.
        for tactic in self.previous:
            sigs.update(tactic.sign())
        relpath = self.target_file.relpath(self.target.directory)
        sigs[relpath] = (self.layer.url,
                         self.kind,
                         utils.sign(self.target_file))
        return sigs


class VersionTactic(Tactic):
    """
    Tactic to generate the ``version`` file with VCS revision info to be
    displayed in ``juju status``.

    This tactic is not part of the normal set of tactics that are matched
    against files.  Instead, it is manually called to generate the ``version``
    file.
    """
    FILENAME = "version"

    CMDS = (
        ('git', 'describe', '--dirty', '--always'),
        ('bzr', 'version-info'),
        ('hg', 'id', '-n'),
    )

    def __init__(self, charm, target, layer, next_config):
        super(VersionTactic, self).__init__(
            charm / self.FILENAME, target, layer, next_config)
        self.charm = charm
        self.wrote_sha = False

    def read(self):
        ""  # suppress inherited doc
        if self.entity.isfile():
            # try to read existing version file
            return self.entity.text()
        return ""

    @property
    def target_file(self):
        ""  # suppress inherited doc
        target = self.target.directory / self.FILENAME
        return target

    @classmethod
    def trigger(cls, entity, target, layer, next_config):
        ""  # suppress inherited doc
        return True

    def _try_to_get_current_sha(self):
        with utils.cd(str(self.charm)):
            for cmd in self.CMDS:
                try:
                    log.debug('Trying to determine version with: '
                              '{}'.format(cmd[0]))
                    sha = utils.Process(cmd)()
                    if sha and sha.exit_code == 0 and sha.output:
                        log.debug('Got version: {}'.format(sha.output))
                        return sha.output
                    else:
                        log.debug('Failed to get version{}'.format(
                            ': {}'.format(sha.output) if sha else ''
                        ))
                        continue
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise
                    log.debug(e)
                    continue
        return ""

    def __call__(self):
        self.target_file.dirname().makedirs_p()
        new_sha = self._try_to_get_current_sha()
        old_sha = self.read()
        if new_sha and old_sha and new_sha != old_sha:
            log.warn(
                ("version {} is out of update, new sha {} "
                 "will be used!").format(old_sha, new_sha))
        sha = new_sha or old_sha
        if sha:
            self.target_file.write_bytes(sha.encode())
            self.wrote_sha = True
        else:
            self.wrote_sha = False

    def sign(self):
        ""  # suppress inherited doc
        if self.wrote_sha:
            return {
                self.target_file.relpath(self.target.directory): (
                    self.layer.url,
                    "dynamic",
                    utils.sign(self.target_file)
                )
            }
        else:
            return {}

    def __str__(self):
        return "Ensuring {}".format(self.entity)


def load_tactic(dpath, basedir):
    """
    Load a tactic from the current layer using a dotted path.

    The final element in the path should be a
    :class:`~charmtools.build.tactics.Tactic` subclass.
    """
    obj = utils.load_class(dpath, basedir)
    if not issubclass(obj, Tactic):
        raise ValueError("Expected to load a tactic for %s" % dpath)
    return obj


def extend_with_default(validator_class):
    """
    Extend a jsonschema validator to propagate default values prior
    to validating.

    Used internally to ensure validation of layer options supports
    default values.
    """
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
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
    CopyrightTactic,
    DistYAML,
    ResourcesYAML,
    MetadataYAML,
    ConfigYAML,
    ActionsYAML,
    LayerYAML,
    CopyTactic
]
