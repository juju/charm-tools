#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import blessings
import json
import logging
import os
import requests
import sys
import uuid
import yaml

import charmtools.build.tactics

from path import Path as path
from collections import OrderedDict
from charmtools import (utils, repofinder, proof)
from charmtools.build import inspector
from charmtools.build.errors import BuildError
from charmtools.build.config import BuildConfig
from charmtools.build.tactics import Tactic, WheelhouseTactic
from charmtools.build.fetchers import (
    InterfaceFetcher,
    LayerFetcher,
    get_fetcher,
    FetchError,
)
from charmtools.version import charm_tools_version

log = logging.getLogger("build")


class Configable(object):
    CONFIG_FILE = None
    OLD_CONFIG_FILE = None

    def __init__(self):
        self._config = BuildConfig()
        self.config_file = self.CONFIG_FILE
        self.old_config_file = self.OLD_CONFIG_FILE

    @property
    def config(self):
        if self._config.configured:
            return self._config
        if self.config_file and self.config_file.exists():
            self._config.configure(self.config_file)
        elif self.old_config_file and self.old_config_file.exists():
            self._config.configure(self.old_config_file)
        return self._config

    @property
    def configured(self):
        return bool(self.config is not None and self.config.configured)


class Fetched(Configable):
    def __init__(self, url, target_repo, name=None):
        super(Fetched, self).__init__()
        self.url = url
        self.target_repo = target_repo / self.NAMESPACE
        self.directory = None
        self._name = name
        self.fetched = False

    @property
    def name(self):
        if self._name:
            return self._name
        if self.url.startswith(self.NAMESPACE):
            return self.url[len(self.NAMESPACE)+1:]
        return self.url.rsplit('/', 1)[-1]

    def __repr__(self):
        return "<{} {}:{}>".format(self.__class__.__name__,
                                   self.url, self.directory)

    def __div__(self, other):
        return self.directory / other

    def fetch(self):
        try:
            fetcher = get_fetcher(self.url)
        except FetchError:
            # We might be passing a local dir path directly
            # which fetchers don't currently  support
            self.directory = path(self.url)
        else:
            if hasattr(fetcher, "path") and fetcher.path.exists():
                self.directory = path(fetcher.path)
            else:
                if not self.target_repo.exists():
                    self.target_repo.makedirs_p()
                self.directory = path(fetcher.fetch(self.target_repo))
                self.fetched = True

        if not self.directory.exists():
            raise BuildError(
                "Unable to locate {}. "
                "Do you need to set {}?".format(
                    self.url, self.ENVIRON))

        if self.config_file:
            self.config_file = self.directory / self.config_file
        if self.old_config_file:
            self.old_config_file = self.directory / self.old_config_file
        self._name = self.config.name
        return self


class Interface(Fetched):
    CONFIG_FILE = "interface.yaml"
    NAMESPACE = "interface"
    ENVIRON = "INTERFACE_PATH"


class Layer(Fetched):
    CONFIG_FILE = "layer.yaml"
    OLD_CONFIG_FILE = "composer.yaml"
    NAMESPACE = "layer"
    ENVIRON = "LAYER_PATH"


class Builder(object):
    """
    Handle the processing of overrides, implements the policy of BuildConfig
    """
    PHASES = ['lint', 'read', 'call', 'sign', 'build']
    HOOK_TEMPLATE_FILE = path('hooks/hook.template')
    DEFAULT_SERIES = 'trusty'
    METRICS_URL = 'http://www.google-analytics.com/collect'
    METRICS_ID = 'UA-96529618-2'

    def __init__(self):
        self.config = BuildConfig()
        self.force = False
        self._name = None
        self._charm = None
        self._top_layer = None
        self.hide_metrics = False
        self.wheelhouse_overrides = None

    @property
    def top_layer(self):
        if not self._top_layer:
            self._top_layer = Layer(self.charm, self.deps).fetch()

        return self._top_layer

    @property
    def charm(self):
        return self._charm

    @charm.setter
    def charm(self, value):
        self._charm = path(value)

    @property
    def charm_metadata(self):
        if not hasattr(self, '_charm_metadata'):
            md = path(self.charm) / "metadata.yaml"
            try:
                setattr(
                    self, '_charm_metadata',
                    yaml.safe_load(md.open()) if md.exists() else None)
            except yaml.YAMLError as e:
                log.debug(e)
                raise BuildError("Failed to process {0}. "
                                 "Ensure the YAML is valid".format(md))

        return self._charm_metadata

    @property
    def name(self):
        if self._name:
            return self._name

        # optionally extract name from the top layer
        self._name = str(path(self.charm).abspath().name)

        # however if the current layer has a metadata.yaml we can
        # use its name
        if self.charm_metadata:
            name = self.charm_metadata.get("name")
            if name:
                self._name = name
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def manifest(self):
        return self.target_dir / '.build.manifest'

    def check_series(self):
        """Make sure this is a either a multi-series charm, or we have a
        build series defined. If not, fall back to a default series.

        """
        if self.series:
            return
        if self.charm_metadata and self.charm_metadata.get('series'):
            return
        self.series = self.DEFAULT_SERIES

    def status(self):
        result = {}
        result.update(vars(self))
        for e in ["LAYER_PATH", "INTERFACE_PATH", "JUJU_REPOSITORY"]:
            result[e] = os.environ.get(e)
        return result

    def create_repo(self):
        # Generated output will go into this directory
        base = path(self.output_dir)
        self.repo = (base / (self.series if self.series else 'builds'))
        # And anything it includes from will be placed here
        # outside the series
        self.deps = (base / "deps")
        self.target_dir = (self.repo / self.name)

    def find_or_create_repo(self, allow_create=True):
        # see if output dir is already in a repo, we can use that directly
        if self.output_dir == path(self.charm).abspath():
            # we've indicated in the cmdline that we are doing an inplace
            # update
            if (self.series and
                    self.output_dir.parent.basename() == self.series):
                # we're already in a repo
                self.repo = self.output_dir.parent.parent
                self.deps = (self.repo / "deps")
                self.target_dir = self.output_dir
                return
        if allow_create:
            self.create_repo()
        else:
            raise ValueError("%s doesn't seem valid", self.charm.directory)
        log.info("Destination charm directory: {}".format(self.target_dir))

    @property
    def layers(self):
        layers = []
        for i in self._layers:
            layers.append(i.url)
        for i in self._interfaces:
            layers.append(i.url)
        layers.append("build")
        return layers

    def fetch(self):
        self.target_dir.makedirs_p()
        if not self.top_layer.configured:
            log.warn("The top level layer expects a "
                     "valid layer.yaml file")
        # Manually create a layer object for the output
        self.target = Layer(self.name, self.repo)
        self.target.directory = self.target_dir
        self.post_metrics('charm', self.name, False)
        return self.fetch_deps(self.top_layer)

    def fetch_deps(self, layer):
        results = {"layers": [], "interfaces": []}
        self.fetch_dep(layer, results)
        # results should now be a bottom up list
        # of deps. Using the in order results traversal
        # we can build out our plan for each file in the
        # output layer
        results["layers"].append(layer)
        self._layers = results["layers"]
        self._interfaces = results["interfaces"]
        return results

    def fetch_dep(self, layer, results):
        # Recursively fetch and scan layers
        # This returns a plan for each file in the result
        baselayers = layer.config.get('includes', [])
        if not baselayers:
            # no deps, this is possible for any base
            # but questionable for the target
            return

        if isinstance(baselayers, str):
            baselayers = [baselayers]

        for base in baselayers:
            # The order of these commands is important. We only want to
            # fetch something if we haven't already fetched it.
            if base.startswith("interface:"):
                iface = Interface(base, self.deps)
                if iface.name in [i.name for i in results['interfaces']]:
                    continue
                results["interfaces"].append(iface.fetch())
                self.post_metrics('interface', iface.name, iface.fetched)
            else:
                base_layer = Layer(base, self.deps)
                if base_layer.name in [i.name for i in results['layers']]:
                    continue
                base_layer.fetch()
                self.fetch_dep(base_layer, results)
                results["layers"].append(base_layer)
                self.post_metrics('layer', base_layer.name, base_layer.fetched)

    def build_tactics(self, entry, layer, next_config, output_files):
        relname = entry.relpath(layer.directory)
        existing_tactic = output_files.get(relname)
        tactic = Tactic.get(
            entry,
            self.target,
            layer,
            next_config,
            existing_tactic,
        )
        output_files[relname] = tactic

    def plan_layers(self, layers, output_files):
        next_config = BuildConfig()
        next_config.add_config(layers["layers"][0].config)

        layers["layers"][-1].url = self.name

        for i, layer in enumerate(layers["layers"]):
            log.info("Processing layer: %s%s", layer.url,
                     "" if 'deps' in layer.directory.splitall()
                     else " (from %s)" % layer.directory.relpath())
            if i + 1 < len(layers["layers"]):
                next_layer = layers["layers"][i + 1]
                next_config = next_config.add_config(next_layer.config)
            else:
                # Add an empty level to the configs to represent that there
                # is no layer after the current one.  This is important for
                # the IgnoreTactic, which needs to look ahead so that it can
                # handle ignoring entire directories.
                next_config = next_config.add_config({})
            list(e for e in utils.walk(layer.directory,
                                       self.build_tactics,
                                       layer=layer,
                                       next_config=next_config,
                                       output_files=output_files))
        if self.wheelhouse_overrides:
            existing_tactic = output_files.get('wheelhouse.txt')
            output_files['wheelhouse.txt'] = WheelhouseTactic(
                str(self.wheelhouse_overrides),
                self.target,
                layers["layers"][-1],
                next_config,
            )
            if existing_tactic is not None:
                output_files['wheelhouse.txt'].combine(existing_tactic)
        plan = [t for t in output_files.values() if t]
        return plan

    def plan_interfaces(self, layers, output_files, plan):
        # Interface includes don't directly map to output files
        # as they are computed in combination with the metadata.yaml
        if not layers.get('interfaces'):
            return
        metadata_tactic = [tactic for tactic in plan if isinstance(
                           tactic, charmtools.build.tactics.MetadataYAML)]
        if not metadata_tactic:
            raise BuildError('At least one layer must provide '
                             'metadata.yaml')
        meta = metadata_tactic[0].process()
        if not meta and layers.get('interfaces'):
            raise BuildError(
                'Includes interfaces but no metadata.yaml to bind them')
        elif self.HOOK_TEMPLATE_FILE not in output_files:
            raise BuildError('At least one layer must provide %s',
                             self.HOOK_TEMPLATE_FILE)
        elif not meta:
            log.warn('Empty metadata.yaml')

        template_file = self.target / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        specs = []
        used_interfaces = set()
        for role in ("provides", "requires", "peers"):
            for k, v in meta.get(role, {}).items():
                # ex: ["provides", "db", "mysql"]
                specs.append([role, k, v["interface"]])
                used_interfaces.add(v["interface"])

        for iface in layers["interfaces"]:
            if iface.name not in used_interfaces:
                # we shouldn't include something the charm doesn't use
                log.warn("layer.yaml includes {} which isn't "
                         "used in metadata.yaml".format(
                             iface.name))
                continue
            for role, relation_name, interface_name in specs:
                if interface_name != iface.name:
                    continue

                log.info("Processing interface: %s%s", interface_name,
                         "" if 'deps' in iface.directory.splitall()
                         else " (from %s)" % iface.directory.relpath())
                # COPY phase
                plan.append(
                    charmtools.build.tactics.InterfaceCopy(
                        iface, relation_name, role,
                        self.target, target_config)
                )
                # Link Phase
                plan.append(
                    charmtools.build.tactics.InterfaceBind(
                        relation_name, iface.url, self.target,
                        target_config, template_file))

    def plan_storage(self, layers, output_files, plan):
        # Storage hooks don't directly map to output files
        # as they are computed in combination with the metadata.yaml
        metadata_tactic = [tactic for tactic in plan if isinstance(
                           tactic, charmtools.build.tactics.MetadataYAML)]
        if not metadata_tactic:
            raise BuildError('At least one layer must provide metadata.yaml')
        meta_tac = metadata_tactic[0]
        meta_tac.process()
        if not meta_tac.storage:
            return
        if self.HOOK_TEMPLATE_FILE not in output_files:
            raise BuildError('At least one layer must provide %s',
                             self.HOOK_TEMPLATE_FILE)

        template_file = self.target / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        for name, owner in meta_tac.storage.items():
            plan.append(
                charmtools.build.tactics.StorageBind(
                    name, owner, self.target,
                    target_config, template_file))

    def formulate_plan(self, layers):
        """Build out a plan for each file in the various
        layers, taking into account config at each layer"""
        output_files = OrderedDict()
        self.plan = self.plan_layers(layers, output_files)
        self.plan_interfaces(layers, output_files, self.plan)
        self.plan_storage(layers, output_files, self.plan)
        return self.plan

    def post_metrics(self, kind, layer_name, fetched):
        if self.hide_metrics:
            return
        conf_file = path('~/.config/charm-build.conf').expanduser()
        if conf_file.exists():
            conf = yaml.safe_load(conf_file.text())
            cid = conf['cid']
        else:
            conf_file.parent.makedirs_p()
            cid = str(uuid.uuid4())
            conf_file.write_text(yaml.dump({'cid': cid}))
        try:
            requests.post(self.METRICS_URL, timeout=10, data={
                'tid': self.METRICS_ID,
                'v': 1,
                'aip': 1,
                't': 'event',
                'ds': 'app',
                'cid': cid,
                'av': charm_tools_version(),
                'an': "charm-build",
                'ec': kind,
                'ea': 'fetch' if fetched else 'local',
                'el': 'name',
                'ev': layer_name,
                'cd1': self.series,
            })
        except requests.exceptions.RequestException:
            pass

    def exec_plan(self, plan=None, layers=None):
        signatures = {}
        cont = True
        for phase in self.PHASES:
            for tactic in plan:
                if phase == "lint":
                    cont &= tactic.lint()
                    if cont is False and self.force is not True:
                        # no message, reason will already have been logged
                        raise BuildError()
                elif phase == "read":
                    # We use a read (into memory phase to make layer comps
                    # simpler)
                    tactic.read()
                elif phase == "call":
                    tactic()
                elif phase == "sign":
                    sig = tactic.sign()
                    if sig:
                        signatures.update(sig)
        new_repo = not self.manifest.exists()
        if new_repo:
            added, changed, removed = set(), set(), set()
        else:
            added, changed, _ = utils.delta_signatures(self.manifest)
            removed = self.clean_removed(signatures)
        # write out the sigs
        if "sign" in self.PHASES:
            self.write_signatures(signatures, layers)
        if self.report:
            self.write_report(new_repo, added, changed, removed)

    def write_signatures(self, signatures, layers):
        signatures['.build.manifest'] = ["build", 'dynamic', 'unchecked']
        self.manifest.write_text(json.dumps(dict(
            signatures=signatures,
            layers=layers,
        ), indent=2, sort_keys=True))

    def generate(self):
        layers = self.fetch()
        self.formulate_plan(layers)
        self.exec_plan(self.plan, self.layers)

    def validate(self):
        self._validate_charm_repo()

        if not self.manifest.exists():
            return [], [], []
        a, c, d = utils.delta_signatures(self.manifest)

        for f in a:
            log.warn(
                "Added unexpected file, should be in a base layer: %s", f)
        for f in c:
            log.warn(
                "Changed file owned by another layer: %s", f)
        for f in d:
            log.warn(
                "Deleted a file owned by another layer: %s", f)
        if a or c or d:
            if self.force is True:
                log.info(
                    "Continuing with known changes to target layer. "
                    "Changes will be overwritten")
            else:
                raise BuildError(
                    "Unable to continue due to unexpected modifications "
                    "(try --force)")

        return a, c, d

    def _validate_charm_repo(self):
        if 'repo' not in self.top_layer.config:
            msg = 'Please add a `repo` key to your {}'.format(
                self.top_layer.config_file.name)
            recommended_repo = repofinder.get_recommended_repo(self.charm)
            if recommended_repo:
                msg += ', e.g. repo: {}'.format(recommended_repo)
            else:
                msg += ', with a url from which your layer can be cloned.'
            log.warn(msg)

    def __call__(self):
        self.find_or_create_repo()

        log.debug(json.dumps(
            self.status(), indent=2, sort_keys=True, default=str))
        self.validate()
        self.generate()

    def inspect(self):
        self.charm = path(self.charm).abspath()
        inspector.inspect(self.charm, force_styling=self.force_raw)

    def normalize_outputdir(self):
        od = path(self.charm).abspath()
        repo = os.environ.get('JUJU_REPOSITORY')
        if repo:
            repo = path(repo)
            if repo.exists():
                od = repo
        elif ":" in od:
            od = od.basename
        self.output_dir = od

    def _check_path(self, path_to_check):
        # have to expand ~user instead of ~ because $HOME is set to snap dir
        home_dir = os.path.expanduser('~{}'.format(os.environ['USER']))
        if home_dir.startswith('~'):  # expansion failed
            raise BuildError('Could not determine home directory')
        return os.path.abspath(path_to_check).startswith(home_dir)

    def check_paths(self):
        paths_to_check = [
            self.output_dir,
            self.wheelhouse_overrides,
            os.environ.get('JUJU_REPOSITORY'),
            os.environ.get('LAYER_PATH'),
            os.environ.get('INTERACE_PATH'),
        ]
        for path_to_check in paths_to_check:
            if path_to_check and not self._check_path(path_to_check):
                raise BuildError('Due to snap confinement, all paths must be '
                                 'under your home directory, including the '
                                 'build output dir, JUJU_REPOSITORY, '
                                 'LAYER_PATH, INTERFACE_PATH, and any '
                                 'wheelhouse overrides')

    def clean_removed(self, signatures):
        """
        Clean up any files that were accounted for in the previous build
        manifest but which have been removed in the current set of sigs.
        """
        old_sigs = json.loads(self.manifest.text())['signatures']
        old_files = set(old_sigs.keys()) - {'.build.manifest'}
        new_files = set(signatures.keys())
        removed = old_files - new_files
        for filename in removed:
            filepath = self.target_dir / filename
            filepath.remove_p()
        return removed

    def write_report(self, new_repo, added, changed, removed):
        """
        Log messages indicating what changed with this (re)build.
        """
        log.info('')
        log.info('---------------------------------------')
        log.info('              Build Report')
        log.info('---------------------------------------')

        if new_repo:
            log.info('New build; all files were modified.')
            return
        elif any([added, changed, removed]):
            sigils = ['+', ' ', '-']
            for sigil, filenames in zip(sigils, [added, changed, removed]):
                for filename in filenames:
                    log.info(' {} {}'.format(sigil, filename))
        else:
            log.info('No new changes; no files were modified.')


def configLogging(build):
    global log
    logging.captureWarnings(True)
    term = os.environ.get('TERM')
    if term and term.startswith('screen.'):
        term = term[7:]
    clifmt = utils.ColoredFormatter(
        blessings.Terminal(term),
        '%(name)s: %(message)s')
    root_logger = logging.getLogger()
    clihandler = logging.StreamHandler(sys.stdout)
    clihandler.setFormatter(clifmt)
    if isinstance(build.log_level, str):
        build.log_level = build.log_level.upper()
    root_logger.setLevel(build.log_level)
    log.setLevel(build.log_level)
    root_logger.addHandler(clihandler)
    requests_logger = logging.getLogger("requests")
    requests_logger.setLevel(logging.WARN)
    urllib_logger = logging.getLogger("urllib3")
    urllib_logger.setLevel(logging.CRITICAL)


def inspect(args=None):
    build = Builder()
    parser = argparse.ArgumentParser(
        description='inspect the layers of a built charm')
    parser.add_argument('-r', '--force-raw', action="store_true",
                        help="Force raw output (color)")
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('charm', nargs="?", default=".", type=path)
    utils.add_plugin_description(parser)
    # Namespace will set the options as attrs of build
    parser.parse_args(args, namespace=build)
    configLogging(build)
    build.inspect()


def deprecated_main():
    namemap = {
        'compose': 'build',
        'generate': 'build',
        'refresh': 'build',
        'inspect': 'layers',
    }
    cmd = sys.argv[0]
    if "-" in cmd:
        old = cmd.rsplit('-', 1)[-1]
    else:
        old = sys.argv[1]
    new = namemap[old]

    class MockBuild(object):
        log_level = 'INFO'

    configLogging(MockBuild)

    msg = "{} has been deprecated, please use {}".format(old, new)
    if '--description' in sys.argv:
        print(msg)
    else:
        log.critical(msg)


def main(args=None):
    build = Builder()
    parser = argparse.ArgumentParser(
        description="build a charm from layers and interfaces",
        formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-f', '--force', action="store_true")
    parser.add_argument('-o', '--output-dir', type=path)
    parser.add_argument('-s', '--series', default=None)
    parser.add_argument('--hide-metrics', dest="hide_metrics",
                        default=False, action="store_true")
    parser.add_argument('--interface-service',
                        default="https://juju.github.io/layer-index/")
    parser.add_argument('--no-local-layers', action="store_true",
                        help="Don't use local layers when building. "
                        "Forces included layers to be downloaded "
                        "from the interface service.")
    parser.add_argument('-n', '--name',
                        help="Build a charm of 'name' from 'charm'")
    parser.add_argument('-r', '--report', action="store_true",
                        help="Show post-build report of changes")
    parser.add_argument('-w', '--wheelhouse-overrides', type=path,
                        help="Provide a wheelhouse.txt file with overrides "
                             "for the built wheelhouse")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Increase output (same as -l DEBUG)")
    parser.add_argument('charm', nargs="?", default=".", type=path)
    utils.add_plugin_description(parser)
    # Namespace will set the options as attrs of build
    parser.parse_args(args, namespace=build)
    if build.charm == "help":
        parser.print_help()
        raise SystemExit(0)

    if build.verbose:
        build.log_level = logging.DEBUG

    # Monkey patch in the domain for the interface webservice
    InterfaceFetcher.INTERFACE_DOMAIN = build.interface_service
    LayerFetcher.INTERFACE_DOMAIN = build.interface_service

    InterfaceFetcher.NO_LOCAL_LAYERS = build.no_local_layers

    configLogging(build)

    try:
        if not build.output_dir:
            build.normalize_outputdir()
        build.check_paths()
        if not build.series:
            build.check_series()

        build()

        lint, exit_code = proof.proof(build.target_dir, False, False)
        llog = logging.getLogger("proof")

        if not lint:
            llog.info('OK!')

        for line in lint:
            if line[0] == "I":
                llog.info(line)
            elif line[0] == "W":
                llog.warn(line)
            elif line[0] == "E":
                llog.error(line)
    except (BuildError, FetchError) as e:
        if e.args:
            log.error(*e.args)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
