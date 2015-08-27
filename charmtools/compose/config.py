from .tactics import DEFAULT_TACTICS, load_tactic


import pathspec
from ruamel import yaml
import logging
from path import path
from otherstuf import chainstuf

DEFAULT_IGNORES = [
    ".bzr/",
    ".git/",
    "**/.ropeproject/",
    "*.pyc",
    "*~",
    ".tox/",
    "build/",
]


class ComposerConfig(chainstuf):
    """Defaults for controlling the generator, each layer in
    the inclusion graph can provide values, including things
    like overrides, or warnings if things are overridden that
    shouldn't be.
    """
    DEFAULT_FILE = "composer.yaml"

    def __init__(self, *args, **kwargs):
        super(ComposerConfig, self).__init__(*args, **kwargs)
        self['_tactics'] = []
        self.configured = False

    def __getattr__(self, key):
        return self[key]

    def rget(self, key):
        """Combine all the results from all the layers into a single iter"""
        result = []
        for m in self.maps:
            r = m.get(key)
            if r:
                if isinstance(r, (list, tuple)):
                    result.extend(r)
                else:
                    result.append(r)
        return result

    def configure(self, config_file, allow_missing=False):
        config_file = path(config_file)
        data = None
        if not config_file.exists() and not allow_missing:
            raise OSError("Missing Config File {}".format(config_file))
        try:
            if config_file.exists():
                data = yaml.load(config_file.open())
                self.configured = True
        except yaml.parser.ParserError:
            logging.critical("Malformed Config file: {}".format(config_file))
            raise
        if data:
            self.update(data)
        # look at any possible imports and use them to build tactics
        tactics = self.get('tactics')
        basedir = config_file.dirname()
        if tactics:
            for name in tactics:
                tactic = load_tactic(name, basedir)
                self._tactics.append(tactic)
        return self

    @classmethod
    def from_config(cls, config_file, allow_missing=False):
        c = cls()
        c.configure(config_file, allow_missing)
        return c

    def add_config(self, config_file, allow_missing=False):
        c = self.new_child()
        c.configure(config_file, allow_missing)
        return c

    @property
    def name(self):
        return self.get('name')

    @property
    def ignores(self):
        return self.rget('ignore') + DEFAULT_IGNORES

    def tactics(self):
        # XXX: combine from config layer
        return self.rget('_tactics') + DEFAULT_TACTICS

    def tactic(self, entity, current, target, next_config):
        # Produce a tactic for the entity in question
        # These will be accumulate through the layers
        # and executed later
        bd = current.directory
        # Ignore handling
        if next_config:
            spec = pathspec.PathSpec.from_lines(pathspec.GitIgnorePattern,
                                                next_config.ignores)
            p = entity.relpath(bd)
            matches = spec.match_files((p,))
            if p in matches:
                return None

        for tactic in self.tactics():
            if tactic.trigger(entity.relpath(bd)):
                return tactic(target=target, entity=entity,
                              current=current, config=next_config)
        return None
