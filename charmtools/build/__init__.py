#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import sys
import warnings

import blessings
from collections import OrderedDict
from path import path
import requests
import yaml
from charmtools.build import inspector
import charmtools.build.tactics
from charmtools.build.config import (BuildConfig, DEFAULT_IGNORES)
from charmtools.build.fetchers import (InterfaceFetcher,
                                       LayerFetcher,
                                       get_fetcher,
                                       FetchError)
from charmtools import utils

log = logging.getLogger("build")


class BuildError(Exception):
    pass


class Configable(object):
    CONFIG_FILE = None

    def __init__(self):
        self._config = BuildConfig()
        self.config_file = None

    @property
    def config(self):
        if self._config.configured:
            return self._config
        if self.config_file and self.config_file.exists():
            self._config.configure(self.config_file)
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

    @property
    def name(self):
        if self._name:
            return self._name
        if self.url.startswith(self.NAMESPACE):
            return self.url[len(self.NAMESPACE)+1:]
        return self.url

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

        if not self.directory.exists():
            raise BuildError(
                "Unable to locate {}. "
                "Do you need to set {}?".format(
                    self.url, self.ENVIRON))

        self.config_file = self.directory / self.CONFIG_FILE
        if not self.config_file.exists():
            if self.OLD_CONFIG and (self.directory / self.OLD_CONFIG).exists():
                self.config_file = (self.directory / self.OLD_CONFIG)
        self._name = self.config.name
        return self


class Interface(Fetched):
    CONFIG_FILE = "interface.yaml"
    OLD_CONFIG = None
    NAMESPACE = "interface"
    ENVIRON = "INTERFACE_PATH"


class Layer(Fetched):
    CONFIG_FILE = "layer.yaml"
    OLD_CONFIG = "composer.yaml"
    NAMESPACE = "layer"
    ENVIRON = "LAYER_PATH"


class Builder(object):
    """
    Handle the processing of overrides, implements the policy of BuildConfig
    """
    PHASES = ['lint', 'read', 'call', 'sign', 'build']
    HOOK_TEMPLATE_FILE = path('hooks/hook.template')

    def __init__(self):
        self.config = BuildConfig()
        self.force = False
        self._name = None
        self._charm = None
        self.hide_metrics = False

    @property
    def charm(self):
        return self._charm

    @charm.setter
    def charm(self, value):
        self._charm = path(value)

    @property
    def name(self):
        if self._name:
            return self._name

        # optionally extract name from the top layer
        self._name = str(path(self.charm).abspath().name)

        # however if the current layer has a metadata.yaml we can
        # use its name
        md = path(self.charm) / "metadata.yaml"
        if md.exists():
            data = yaml.load(md.open())
            name = data.get("name")
            if name:
                self._name = name
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def charm_name(self):
        return "{}/{}".format(self.series, self.name)

    def status(self):
        result = {}
        result.update(vars(self))
        for e in ["LAYER_PATH", "INTERFACE_PATH", "JUJU_REPOSITORY"]:
            result[e] = os.environ.get(e)
        return result

    def create_repo(self):
        # Generated output will go into this directory
        base = path(self.output_dir)
        self.repo = (base / self.series)
        # And anything it includes from will be placed here
        # outside the series
        self.deps = (base / "deps")
        self.target_dir = (self.repo / self.name)

    def find_or_create_repo(self, allow_create=True):
        # see if output dir is already in a repo, we can use that directly
        if self.output_dir == path(self.charm).normpath():
            # we've indicated in the cmdline that we are doing an inplace
            # update
            if self.output_dir.parent.basename() == self.series:
                # we're already in a repo
                self.repo = self.output_dir.parent.parent
                self.deps = (self.repo / "deps")
                self.target_dir = self.output_dir
                return
        if allow_create:
            self.create_repo()
        else:
            raise ValueError("%s doesn't seem valid", self.charm.directory)

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
        layer = Layer(self.charm, self.deps).fetch()
        if not layer.configured:
            log.warn("The top level layer expects a "
                     "valid layer.yaml file")
        # Manually create a layer object for the output
        self.target = Layer(self.name, self.repo)
        self.target.directory = self.target_dir
        return self.fetch_deps(layer)

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
            if base.startswith("interface:"):
                iface = Interface(base, self.deps).fetch()
                if iface.name in [i.name for i in results['interfaces']]:
                    continue
                results["interfaces"].append(iface)
            else:
                base_layer = Layer(base, self.deps).fetch()
                self.fetch_dep(base_layer, results)
                if base_layer.name in [i.name for i in results['layers']]:
                    continue
                results["layers"].append(base_layer)

    def build_tactics(self, entry, current, config, output_files):
        # Delegate to the config object, it's rules
        # will produce a tactic
        relname = entry.relpath(current.directory)
        current = current.config.tactic(entry, current, self.target, config)
        existing = output_files.get(relname)
        if existing is not None:
            tactic = current.combine(existing)
        else:
            tactic = current
        output_files[relname] = tactic

    def plan_layers(self, layers, output_files):
        config = BuildConfig()
        cfgfn = layers["layers"][0] / BuildConfig.DEFAULT_FILE
        if cfgfn.exists():
            config = config.add_config(
                cfgfn, True)
        else:
            cfgfn = layers["layers"][0] / BuildConfig.OLD_CONFIG
            config = config.add_config(
                cfgfn, True)

        layers["layers"][-1].url = self.name

        for i, layer in enumerate(layers["layers"]):
            log.info("Processing layer: %s", layer.url)
            if i + 1 < len(layers["layers"]):
                next_layer = layers["layers"][i + 1]
                config = config.add_config(
                    next_layer / BuildConfig.DEFAULT_FILE, True)
            list(e for e in utils.walk(layer.directory,
                                       self.build_tactics,
                                       current=layer,
                                       config=config,
                                       output_files=output_files))
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
            raise BuildError('At least one layer must provide metadata.yaml')
        meta = metadata_tactic[0].process()
        if not meta and layers.get('interfaces'):
            raise BuildError('Includes interfaces but no metadata.yaml to bind them')
        elif self.HOOK_TEMPLATE_FILE not in output_files:
            raise BuildError('At least one layer must provide %s',
                             self.HOOK_TEMPLATE_FILE)
        elif not meta:
            log.warn('Empty metadata.yaml')

        template_file = self.target / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        specs = []
        used_interfaces = set()
        for kind in ("provides", "requires", "peers"):
            for k, v in meta.get(kind, {}).items():
                # ex: ["provides", "db", "mysql"]
                specs.append([kind, k, v["interface"]])
                used_interfaces.add(v["interface"])

        for iface in layers["interfaces"]:
            if iface.name not in used_interfaces:
                # we shouldn't include something the charm doesn't use
                log.warn("layer.yaml includes {} which isn't "
                         "used in metadata.yaml".format(
                             iface.name))
                continue
            for kind, relation_name, interface_name in specs:
                if interface_name != iface.name:
                    continue

                log.info("Processing interface: %s", interface_name)
                # COPY phase
                plan.append(
                    charmtools.build.tactics.InterfaceCopy(
                        iface, relation_name,
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
        if self.hide_metrics is not True:
            self.post_metrics(layers)
        return self.plan

    def post_metrics(self, layers):
        url = "/".join((self.interface_service,
                        "api/v1/metrics/"))
        data = {"kind": "build",
                "layers": [l.url for l in layers["layers"]],
                "interfaces": [i.url for i in layers["interfaces"]]}
        try:
            requests.post(url, json.dumps(data).encode('utf-8'), timeout=10)
        except requests.exceptions.RequestException:
            log.warning("Unable to post usage metrics")

    def exec_plan(self, plan=None, layers=None):
        signatures = {}
        cont = True
        for phase in self.PHASES:
            for tactic in plan:
                if phase == "lint":
                    cont &= tactic.lint()
                    if cont is False and self.force is not True:
                        return
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
        # write out the sigs
        if "sign" in self.PHASES:
            self.write_signatures(signatures, layers)

    def write_signatures(self, signatures, layers):
        sigs = self.target / ".build.manifest"
        signatures['.build.manifest'] = ["build", 'dynamic', 'unchecked']
        sigs.write_text(json.dumps(dict(
            signatures=signatures,
            layers=layers,
        ), indent=2))

    def generate(self):
        layers = self.fetch()
        self.formulate_plan(layers)
        self.exec_plan(self.plan, self.layers)

    def validate(self):
        p = self.target_dir / ".build.manifest"
        if not p.exists():
            return [], [], []
        ignorer = utils.ignore_matcher(DEFAULT_IGNORES)
        a, c, d = utils.delta_signatures(p, ignorer)

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
                raise ValueError(
                    "Unable to continue due to unexpected modifications "
                    "(try --force)")
        return a, c, d

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
        od = path(self.charm).normpath()
        repo = os.environ.get('JUJU_REPOSITORY')
        if repo:
            repo = path(repo)
            if repo.exists():
                od = repo
        elif ":" in od:
            od = od.basename
        log.info("Composing into {}".format(od))
        self.output_dir = od


def configLogging(build):
    global log
    logging.captureWarnings(True)
    clifmt = utils.ColoredFormatter(
        blessings.Terminal(),
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
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--force-raw', action="store_true",
                        help="Force raw output (color)")
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('charm', nargs="?", default=".", type=path)
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
    warnings.warn("{} has been deprecated, please use {}".format(old, new),
                  DeprecationWarning)
    if cmd == "inspect":
        inspect()
    else:
        main()


def main(args=None):
    build = Builder()
    parser = argparse.ArgumentParser(
        description="Build a charm from layers and interfaces.",
        formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-f', '--force', action="store_true")
    parser.add_argument('-o', '--output-dir', type=path)
    parser.add_argument('-s', '--series', default="trusty")
    parser.add_argument('--hide-metrics', dest="hide_metrics",
                        default=False, action="store_true")
    parser.add_argument('--interface-service',
                        default="http://interfaces.juju.solutions")
    parser.add_argument('-n', '--name',
                        help="Build a charm of 'name' from 'charm'")
    parser.add_argument('charm', nargs="?", default=".", type=path)
    # Namespace will set the options as attrs of build
    parser.parse_args(args, namespace=build)
    if build.charm == "help":
        parser.print_help()
        raise SystemExit(0)

    # Monkey patch in the domain for the interface webservice
    InterfaceFetcher.INTERFACE_DOMAIN = build.interface_service
    LayerFetcher.INTERFACE_DOMAIN = build.interface_service
    configLogging(build)

    if not build.output_dir:
        build.normalize_outputdir()
    try:
        build()
    except BuildError as e:
        log.error(*e.args)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
