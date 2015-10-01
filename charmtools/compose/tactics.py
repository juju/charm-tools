import logging
import json
from ruamel import yaml

from path import path
from charmtools import utils

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

    def __init__(self, entity, current, target, config):
        self.entity = entity
        self._current = current
        self._target = target
        self._raw_data = None
        self._config = config

    def __call__(self):
        raise NotImplementedError

    def __str__(self):
        return "{}: {} -> {}".format(
            self.__class__.__name__, self.entity, self.target_file)

    @property
    def current(self):
        """The file in the current layer under consideration"""
        return self._current

    @property
    def target(self):
        """The target (final) layer."""
        return self._target

    @property
    def relpath(self):
        return self.entity.relpath(self.current.directory)

    @property
    def target_file(self):
        target = self.target.directory / self.relpath
        return target

    @property
    def layer_name(self):
        return self.current.directory.name

    @property
    def repo_path(self):
        return path("/".join(self.current.directory.splitall()[-2:]))

    @property
    def config(self):
        # Return the config of the layer *above* you
        # as that is the one that controls your compositing
        return self._config

    def combine(self, existing):
        """Produce a tactic informed by the last tactic for an entry.
        This is when a rule in a higher level charm overrode something in
        one of its bases for example."""
        return self

    @classmethod
    def trigger(cls, relpath):
        """Should the rule trigger for a given path object"""
        return False

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        target = self.target_file
        sig = {}
        if target.exists() and target.isfile():
            sig[self.relpath] = (self.current.url,
                                 self.kind,
                                 utils.sign(self.target_file))
        return sig

    def lint(self):
        return True

    def read(self):
        return None

    def build(self):
        pass


class ExactMatch(object):
    FILENAME = None

    @classmethod
    def trigger(cls, relpath):
        return cls.FILENAME == relpath


class CopyTactic(Tactic):
    def __call__(self):
        if self.entity.isdir():
            return
        should_ignore = utils.ignore_matcher(self.target.config.ignores)
        if not should_ignore(self.relpath):
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
    def trigger(cls, relpath):
        return True


class InterfaceCopy(Tactic):
    def __init__(self, interface, relation_name, target, config):
        self.interface = interface
        self.relation_name = relation_name
        self._target = target
        self._config = config

    @property
    def target(self):
        return self._target / "hooks/relations" / self.interface.name

    def __call__(self):
        # copy the entire tree into the
        # hooks/relations/<interface>
        # directory
        log.debug("Copying Interface %s: %s",
                  self.interface.name, self.target)
        # Ensure the path exists
        if self.target.exists():
            # XXX: fix this to do actual updates
            return
        ignorer = utils.ignore_matcher(self.config.ignores)
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
        for entry in self.interface.directory.walkfiles():
            if entry.splitext()[1] != ".py":
                continue
            relpath = entry.relpath(self._target.directory)
            target = self._target.directory / relpath
            if not target.exists():
                continue
            return utils.delta_python_dump(entry, target,
                                           from_name=relpath)


class InterfaceBind(InterfaceCopy):
    def __init__(self, interface, relation_name, kind, target, config):
        self.interface = interface
        self.relation_name = relation_name
        self.kind = kind
        self._target = target
        self._config = config

    DEFAULT_BINDING = """#!/usr/bin/env python

# Load modules from $CHARM_DIR/lib
import sys
sys.path.append('lib')

# This will load and run the appropriate @hook and other decorated
# handlers from $CHARM_DIR/reactive, $CHARM_DIR/hooks/reactive,
# and $CHARM_DIR/hooks/relations.
#
# See https://jujucharms.com/docs/stable/getting-started-with-charms-reactive
# for more information on this pattern.
from charms.reactive import main
main('{}')
"""

    def __call__(self):
        for hook in ['joined', 'changed', 'broken', 'departed']:
            target = self._target / "hooks" / "{}-relation-{}".format(
                self.relation_name, hook)
            if target.exists():
                # XXX: warn
                continue
            target.parent.makedirs_p()
            target.write_text(self.DEFAULT_BINDING.format(self.relation_name))
            target.chmod(0755)

    def sign(self):
        """return sign in the form {relpath: (origin layer, SHA256)}
        """
        sigs = {}
        for hook in ['joined', 'changed', 'broken', 'departed']:
            target = self._target / "hooks" / "{}-relation-{}".format(
                self.relation_name, hook)
            rel = target.relpath(self._target.directory)
            sigs[rel] = (self.interface.url,
                         "dynamic",
                         utils.sign(target))
        return sigs

    def __str__(self):
        return "Bind Interface {}".format(self.interface.name)


class ManifestTactic(ExactMatch, Tactic):
    FILENAME = ".composer.manifest"

    def __call__(self):
        # Don't copy manifests, they are regenerated
        pass


class SerializedTactic(ExactMatch, Tactic):
    kind = "dynamic"

    def __init__(self, *args, **kwargs):
        super(SerializedTactic, self).__init__(*args, **kwargs)
        self.data = None

    def combine(self, existing):
        # Invoke the previous tactic
        existing()
        if existing.data is not None:
            self.data = existing.data
        return self

    def __call__(self):
        data = self.load(self.entity.open())
        # self.data represents the product of previous layers
        if self.data:
            data = utils.deepmerge(self.data, data)

        # Now apply any rules from config
        config = self.config
        if config:
            section = config.get(self.section)
            if section:
                dels = section.get('deletes', [])
                if self.prefix:
                    namespace = data[self.prefix]
                else:
                    namespace = data
                for key in dels:
                    utils.delete_path(key, namespace)
        self.data = data
        if not self.target_file.parent.exists():
            self.target_file.parent.makedirs_p()
        self.dump(data)
        return data


class YAMLTactic(SerializedTactic):
    """Rule Driven YAML generation"""
    prefix = None

    def load(self, fn):
        return yaml.load(fn, Loader=yaml.RoundTripLoader)

    def dump(self, data):
        yaml.dump(data, self.target_file.open('w'),
                  Dumper=yaml.RoundTripDumper,
                  default_flow_style=False)


class JSONTactic(SerializedTactic):
    """Rule Driven JSON generation"""
    prefix = None

    def load(self, fn):
        return json.load(fn)

    def dump(self, data):
        json.dump(data, self.target_file.open('w'), indent=2)


class ComposerYAML(YAMLTactic, ExactMatch):
    FILENAME = "composer.yaml"

    def read(self):
        self._raw_data = self.load(self.entity.open())

    def __call__(self):
        # rewrite includes to be the current source
        data = self._raw_data
        if data is None:
            return
        # The split should result in the series/charm path only
        # XXX: there will be strange interactions with cs: vs local:
        if 'is' not in data:
            data['is'] = str(self.current.url)
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


class MetadataYAML(YAMLTactic):
    """Rule Driven metadata.yaml generation"""
    section = "metadata"
    FILENAME = "metadata.yaml"
    KEY_ORDER = ["name", "summary", "maintainer",
                 "description", "tags",
                 "requires", "provides", "peers"]

    def dump(self, data):
        if not data:
            return
        final = yaml.comments.CommentedMap()
        # assempt keys in know order
        for k in self.KEY_ORDER:
            if k in data:
                final[k] = data[k]
        missing = set(data.keys()) - set(self.KEY_ORDER)
        for k in sorted(missing):
            final[k] = data[k]
        super(MetadataYAML, self).dump(final)


class ConfigYAML(MetadataYAML):
    """Rule driven config.yaml generation"""
    section = "config"
    prefix = "options"
    FILENAME = "config.yaml"


class InstallerTactic(Tactic):
    def __str__(self):
        return "Installing software to {}".format(self.relpath)

    @classmethod
    def trigger(cls, relpath):
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
        cwd = path.getcwd()
        with utils.tempdir() as temp_dir:
            # We do this dance so we don't have
            # to guess package and .egg file names
            # we move everything in the tempdir to the target
            # and track it for later use in sign()
            utils.Process(("pip",
                           "install",
                           "-t",
                           temp_dir,
                           spec)).throw_on_error()()
            dirs = temp_dir.listdir()
            self._tracked = []
            for d in dirs:
                rp = d.relpath(temp_dir)
                dst = cwd / target / rp
                if dst.exists():
                    if dst.isdir():
                        dst.rmtree_p()
                    elif dst.isfile():
                        dst.remove()
                if not target.exists():
                    target.makedirs_p()
                logging.debug("Installer moving {} to {}".format(d, dst))
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
                    sigs[relpath] = (self.current.url, "dynamic", sig)
            elif d.isfile():
                relpath = d.relpath(self.target.directory)
                sigs[relpath] = (
                    self.current.url, "dynamic", utils.sign(d))
        return sigs


def load_tactic(dpath, basedir):
    """Load a tactic from the current layer using a dotted path. The last
    element in the path should be a Tactic subclass
    """
    obj = utils.load_class(dpath, basedir)
    if not issubclass(obj, Tactic):
        raise ValueError("Expected to load a tactic for %s" % dpath)
    return obj


DEFAULT_TACTICS = [
    ManifestTactic,
    InstallerTactic,
    MetadataYAML,
    ConfigYAML,
    ComposerYAML,
    CopyTactic
]
