#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import sys

import blessings
from collections import OrderedDict
from path import path
import yaml
from charmtools.compose import inspector
import charmtools.compose.tactics
from charmtools.compose.config import (ComposerConfig, DEFAULT_IGNORES)
from charmtools.compose.fetchers import (InterfaceFetcher,
                                         LayerFetcher,
                                         get_fetcher,
                                         FetchError)
from charmtools import utils

log = logging.getLogger("composer")


class Configable(object):
    CONFIG_FILE = None

    def __init__(self):
        self._config = ComposerConfig()
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
        self.target_repo = target_repo
        self.directory = None
        self._name = name

    @property
    def name(self):
        if self._name:
            return self._name
        if self.url.startswith(self.NAMESPACE):
            return self.url[len(self.NAMESPACE):]
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
            raise OSError(
                "Unable to locate {}. "
                "Do you need to set {}?".format(
                    self.url, self.ENVIRON))

        self.config_file = self.directory / self.CONFIG_FILE
        self._name = self.config.name
        return self


class Interface(Fetched):
    CONFIG_FILE = "interface.yaml"
    NAMESPACE = "interface"
    ENVIRON = "INTERFACE_PATH"


class Layer(Fetched):
    CONFIG_FILE = "composer.yaml"
    NAMESPACE = "layer"
    ENVIRON = "COMPOSER_PATH"


class Composer(object):
    """
    Handle the processing of overrides, implements the policy of ComposerConfig
    """
    PHASES = ['lint', 'read', 'call', 'sign', 'build']

    def __init__(self):
        self.config = ComposerConfig()
        self.force = False
        self._name = None
        self._charm = None

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
        for e in ["COMPOSER_PATH", "INTERFACE_PATH", "JUJU_REPOSITORY"]:
            result[e] = os.environ.get(e)
        return result

    def create_repo(self):
        # Generated output will go into this directory
        base = path(self.output_dir)
        self.repo = (base / self.series)
        # And anything it includes from will be placed here
        # outside the series
        self.deps = (base / "deps" / self.series)
        self.target_dir = (self.repo / self.name)

    def find_or_create_repo(self, allow_create=True):
        # see if output dir is already in a repo, we can use that directly
        if self.output_dir == path(self.charm).normpath():
            # we've indicated in the cmdline that we are doing an inplace
            # update
            if self.output_dir.parent.basename() == self.series:
                # we're already in a repo
                self.repo = self.output_dir.parent.parent
                self.deps = (self.repo / "deps" / self.series)
                self.target_dir = self.output_dir
                return
        if allow_create:
            self.create_repo()
        else:
            raise ValueError("%s doesn't seem valid", self.charm.directory)

    def fetch(self):
        layer = Layer(self.charm, self.deps).fetch()
        if not layer.configured:
            log.info("The top level layer expects a "
                     "valid composer.yaml file, "
                     "using defaults.")
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

    @property
    def layers(self):
        layers = []
        for i in self._layers:
            layers.append(i.url)
        for i in self._interfaces:
            layers.append(i.url)
        layers.append("composer")
        return layers

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
                results["interfaces"].append(iface)
            else:
                base_layer = Layer(base, self.deps).fetch()
                self.fetch_dep(base_layer, results)
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
        config = ComposerConfig()
        config = config.add_config(
            layers["layers"][0] / ComposerConfig.DEFAULT_FILE, True)

        layers["layers"][-1].url = self.name

        for i, layer in enumerate(layers["layers"]):
            log.info("Processing layer: %s", layer.url)
            if i + 1 < len(layers["layers"]):
                next_layer = layers["layers"][i + 1]
                config = config.add_config(
                    next_layer / ComposerConfig.DEFAULT_FILE, True)
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
        charm_meta = output_files.get("metadata.yaml")
        if charm_meta:
            meta = charm_meta()
            if not meta:
                return
            target_config = layers["layers"][-1].config
            specs = []
            used_interfaces = set()
            for kind in ("provides", "requires", "peer"):
                for k, v in meta.get(kind, {}).items():
                    # ex: ["provides", "db", "mysql"]
                    specs.append([kind, k, v["interface"]])
                    used_interfaces.add(v["interface"])

            for iface in layers["interfaces"]:
                if iface.name not in used_interfaces:
                    # we shouldn't include something the charm doesn't use
                    log.warn("composer.yaml includes {} which isn't "
                             "used in metadata.yaml".format(
                                 iface.name))
                    continue
                for kind, relation_name, interface_name in specs:
                    if interface_name != iface.name:
                        continue

                    log.info("Processing interface: %s", interface_name)
                    # COPY phase
                    plan.append(
                        charmtools.compose.tactics.InterfaceCopy(
                            iface, relation_name,
                            self.target, target_config)
                    )
                    # Link Phase
                    plan.append(
                        charmtools.compose.tactics.InterfaceBind(
                            iface, relation_name, kind,
                            self.target, target_config))
        elif not charm_meta and layers["interfaces"]:
            raise ValueError(
                "Includes interfaces but no metadata.yaml to bind them")

    def formulate_plan(self, layers):
        """Build out a plan for each file in the various composed
        layers, taking into account config at each layer"""
        output_files = OrderedDict()
        self.plan = self.plan_layers(layers, output_files)
        self.plan_interfaces(layers, output_files, self.plan)
        return self.plan

    def exec_plan(self, plan=None, layers=None):
        signatures = {}
        cont = True
        for phase in self.PHASES:
            for tactic in plan:
                if phase == "lint":
                    cont &= tactic.lint()
                    if cont is False and self.force is not True:
                        break
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
                elif phase == "build":
                    tactic.build()
        # write out the sigs
        if "sign" in self.PHASES:
            self.write_signatures(signatures, layers)

    def write_signatures(self, signatures, layers):
        sigs = self.target / ".composer.manifest"
        signatures['.composer.manifest'] = ["composer", 'dynamic', 'unchecked']
        sigs.write_text(json.dumps(dict(
            signatures=signatures,
            layers=layers,
        ), indent=2))

    def generate(self):
        layers = self.fetch()
        self.formulate_plan(layers)
        self.exec_plan(self.plan, self.layers)

    def validate(self):
        p = self.target_dir / ".composer.manifest"
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
                    "Unable to continue due to unexpected modifications (try --force)")
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


def configLogging(composer):
    global log
    clifmt = utils.ColoredFormatter(
        blessings.Terminal(),
        '%(name)s: %(message)s')
    root_logger = logging.getLogger()
    clihandler = logging.StreamHandler(sys.stdout)
    clihandler.setFormatter(clifmt)
    if isinstance(composer.log_level, str):
        composer.log_level = composer.log_level.upper()
    root_logger.setLevel(composer.log_level)
    log.setLevel(composer.log_level)
    root_logger.addHandler(clihandler)
    requests_logger = logging.getLogger("requests")
    requests_logger.setLevel(logging.WARNING)


def inspect(args=None):
    composer = Composer()
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--force-raw', action="store_true",
                       help="Force raw output (color)")
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('charm', nargs="?", default=".", type=path)
    # Namespace will set the options as attrs of composer
    parser.parse_args(args, namespace=composer)
    configLogging(composer)
    composer.inspect()


def main(args=None):
    composer = Composer()
    parser = argparse.ArgumentParser(
        description="Compose layers into a charm",
        formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-f', '--force', action="store_true")
    parser.add_argument('-o', '--output-dir', type=path)
    parser.add_argument('-s', '--series', default="trusty")
    parser.add_argument('--interface-service',
                        default="http://interfaces.juju.solutions")
    parser.add_argument('-n', '--name',
                        help="Generate a charm of 'name' from 'charm'")
    parser.add_argument('charm', nargs="?", default=".", type=path)
    # Namespace will set the options as attrs of composer
    parser.parse_args(args, namespace=composer)
    # Monkey patch in the domain for the interface webservice
    InterfaceFetcher.INTERFACE_DOMAIN = composer.interface_service
    LayerFetcher.INTERFACE_DOMAIN = composer.interface_service
    configLogging(composer)

    if not composer.output_dir:
        composer.normalize_outputdir()

    composer()


if __name__ == '__main__':
    main()
