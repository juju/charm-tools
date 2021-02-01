from .tactics import load_tactic


from ruamel import yaml
import logging
from path import Path as path
from otherstuf import chainstuf

DEFAULT_IGNORES = [
    ".bzr",
    ".git",
    "**/.ropeproject",
    "*.pyc",
    "*~",
    ".tox",
    "*.swp",
    ".pull-source-rev",
    "*.charm",
    "build.lock",
]


class BuildConfig(chainstuf):
    """Defaults for controlling the generator, each layer in
    the inclusion graph can provide values, including things
    like overrides, or warnings if things are overridden that
    shouldn't be.
    """

    def __init__(self, *args, **kwargs):
        super(BuildConfig, self).__init__(*args, **kwargs)
        self['_tactics'] = self.get('tactics', [])
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
            if config_file.exists() and config_file.text('utf-8').strip():
                data = yaml.safe_load(config_file.open(encoding='utf-8'))
                self.configured = True
        except yaml.error.YAMLError as e:
            logging.critical("Malformed config file {}: {}".format(config_file,
                                                                   e))
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

    def add_config(self, config):
        new_config = self.new_child()
        new_config.update(config)
        return new_config

    @property
    def name(self):
        return self.get('name')

    @property
    def tactics(self):
        return self.rget('_tactics')

    @property
    def ignores(self):
        """
        The ignores for this layer (lower layers are not included).
        """
        ignores = list(DEFAULT_IGNORES)
        if self.maps:
            ignores.extend(self.maps[0].get('ignore', []))
        return ignores

    @property
    def excludes(self):
        """
        The excludes for this layer (lower layers are not included).
        """
        excludes = list(DEFAULT_IGNORES)
        if self.maps:
            excludes.extend(self.maps[0].get('exclude', []))
        return excludes
