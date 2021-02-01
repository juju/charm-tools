#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import blessings
import curses
import json
import logging
import os
import requests
import sys
import uuid
import yaml
import string
import traceback

import charmtools.build.tactics

from path import Path as path
from collections import OrderedDict
from charmtools import (utils, repofinder, proof)
from charmtools.build import inspector
from charmtools.build.errors import BuildError
from charmtools.build.config import BuildConfig, DEFAULT_IGNORES
from charmtools.build.tactics import Tactic, WheelhouseTactic
from charmtools.build.fetchers import (
    InterfaceFetcher,
    LayerFetcher,
    get_fetcher,
    FetchError,
    RepoFetcher,
)
from charmtools.version import cached_charm_tools_version, format_version
from zipfile import ZipFile, ZIP_DEFLATED

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
    def __init__(self, url, target_repo, name=None, lock=None,
                 use_branches=False):
        super(Fetched, self).__init__()
        self.url = url
        self.target_repo = target_repo / self.NAMESPACE
        self.directory = None
        self._name = name
        self.fetched = False
        self.fetched_url = None
        self.vcs = None
        self.revision = None
        self.branch = None
        self.lock = lock
        self.use_branches = use_branches

    @property
    def name(self):
        if self._name:
            return self._name
        if self.url.startswith(self.NAMESPACE + ':'):
            return self.url[len(self.NAMESPACE) + 1:]
        return self.url.rsplit('/', 1)[-1]

    def __repr__(self):
        return "<{} {}:{}>".format(self.__class__.__name__,
                                   self.url, self.directory)

    def __div__(self, other):
        return self.directory / other

    def fetch(self):
        try:
            # In order to lock the fetcher we need to adjust the self.url
            # to get the right thing.  Curiously, self.url is actually
            # "layer:something" here, and so we can match on that.
            if self.lock:
                url = make_url_from_lock_for_layer(
                    self.lock, self.use_branches)
            else:
                url = self.url
            fetcher = get_fetcher(url)
        except FetchError:
            # We might be passing a local dir path directly
            # which fetchers don't currently  support
            self.directory = path(self.url)
            self.revision = RepoFetcher(self.url).get_revision(self.url)
        else:
            if hasattr(fetcher, "path") and fetcher.path.exists():
                self.directory = path(fetcher.path)
            else:
                if not self.target_repo.exists():
                    self.target_repo.makedirs_p()
                self.directory = path(fetcher.fetch(self.target_repo))
                self.fetched = True
                self.fetched_url = getattr(fetcher, "fetched_url", None)
                self.vcs = getattr(fetcher, "vcs", None)
            self.revision = fetcher.get_revision(self.directory)
            self.branch = fetcher.get_branch_for_revision(self.directory,
                                                          self.revision)

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
    ENVIRON = "CHARM_INTERFACES_DIR"
    OLD_ENVIRON = "INTERFACE_PATH"


class Layer(Fetched):
    CONFIG_FILE = "layer.yaml"
    OLD_CONFIG_FILE = "composer.yaml"
    NAMESPACE = "layer"
    ENVIRON = "CHARM_LAYERS_DIR"
    OLD_ENVIRON = "LAYER_PATH"


class Builder(object):
    """
    Handle the processing of overrides, implements the policy of BuildConfig
    """
    PHASES = ['lint', 'read', 'call', 'sign', 'build']
    HOOK_TEMPLATE_FILE = path('hooks/hook.template')
    DEFAULT_SERIES = 'trusty'
    METRICS_URL = 'https://www.google-analytics.com/collect'
    METRICS_ID = 'UA-96529618-2'

    def __init__(self):
        self.config = BuildConfig()
        self.force = False
        self._name = None
        self._charm = None
        self._top_layer = None
        self.hide_metrics = os.environ.get('CHARM_HIDE_METRICS', False)
        self.wheelhouse_overrides = None
        self.wheelhouse_per_layer = False
        self._warned_home = False
        self.lock_items = []
        self.with_locks = {}
        self.charm_file = False

    @property
    def top_layer(self):
        if not self._top_layer:
            # NOTE: no lock for branches for lop layer.
            self._top_layer = Layer(self.charm, self.cache_dir).fetch()

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

        if self.charm is None:
            return None

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
    def source_dir(self):
        return self.top_layer.directory

    @property
    def target_dir(self):
        return self.build_dir / self.name

    @property
    def manifest(self):
        return self.target_dir / '.build.manifest'

    @property
    def lock_file(self):
        return self.source_dir / 'build.lock'

    def check_series(self):
        """Make sure this is a either a multi-series charm, or we have a
        build series defined. If not, fall back to a default series.

        """
        if self.charm_metadata and self.charm_metadata.get('series'):
            return
        elif self.series:
            log.warn('DEPRECATED: use of --series flag; '
                     'specify series in metadata.yaml instead')
            return
        else:
            log.warn('DEPRECATED: implicit series; '
                     'specify series in metadata.yaml instead')

    def status(self):
        result = {}
        result.update(vars(self))
        for e in ["CHARM_LAYERS_DIR",
                  "CHARM_INTERFACES_DIR",
                  "CHARM_BUILD_DIR",
                  "JUJU_REPOSITORY",
                  "LAYER_PATH",
                  "INTERFACE_PATH"]:
            result[e] = os.environ.get(e)
        return result

    def find_or_create_target(self):
        log.info("Destination charm directory: {}".format(self.target_dir))
        self.target_dir.makedirs_p()

    @property
    def layers(self):
        layers = []
        for layer in (self._layers, self._interfaces):
            for i in layer:
                item = {
                    'url': i.url,
                    'rev': i.revision,
                }
                for opt in ('branch', 'fetched_url'):
                    attr = getattr(i, opt, None)
                    if attr:
                        item[opt] = attr
                layers.append(item)
        return layers

    def fetch(self):
        self.target_dir.makedirs_p()
        if not self.top_layer.configured:
            log.warn("The top level layer expects a "
                     "valid layer.yaml file")
        # Manually create a layer object for the output
        self.target = Layer(self.name, self.build_dir,
                            lock=self.lock_for(self.name),
                            use_branches=getattr(self,
                                                 'use_lock_file_branches',
                                                 False))
        self.target.directory = self.target_dir
        self.post_metrics('charm', self.name, False)
        return self.fetch_deps(self.top_layer)

    def fetch_deps(self, layer):
        self.cache_dir.makedirs_p()
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
                iface = Interface(base, self.cache_dir,
                                  lock=self.lock_for(base),
                                  use_branches=getattr(
                                      self, 'use_lock_file_branches', False))
                if iface.name in [i.name for i in results['interfaces']]:
                    continue
                results["interfaces"].append(iface.fetch())
                self.post_metrics('interface', iface.name, iface.fetched)
            else:
                base_layer = Layer(base, self.cache_dir,
                                   lock=self.lock_for(base),
                                   use_branches=getattr(
                                       self, 'use_lock_file_branches', False))
                if base_layer.name in [i.name for i in results['layers']]:
                    continue
                base_layer.fetch()
                self.fetch_dep(base_layer, results)
                results["layers"].append(base_layer)
                self.post_metrics('layer', base_layer.name, base_layer.fetched)

    def lock_for(self, base):
        """Return a lock description for an item 'base' if it exists."""
        return self.with_locks.get(base, {})

    def build_tactics(self, entry, layer, next_config, current_config,
                      output_files):
        relname = entry.relpath(layer.directory)
        existing_tactic = output_files.get(relname)
        tactic = Tactic.get(
            entry,
            self.target,
            layer,
            next_config,
            current_config,
            existing_tactic,
        )
        output_files[relname] = tactic

    def plan_layers(self, layers, output_files):
        current_config = BuildConfig()
        next_config = current_config.add_config(layers["layers"][0].config)

        layers["layers"][-1].url = self.name

        for i, layer in enumerate(layers["layers"]):
            log.info("Processing layer: %s%s", layer.url,
                     "" if layer.directory.startswith(self.cache_dir)
                     else " (from %s)" % layer.directory.relpath())
            current_config = current_config.add_config(layer.config)
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
                                       current_config=current_config,
                                       output_files=output_files))
        # now we do update the wheelhouse.txt output file with the lock file if
        # necessary.
        if not getattr(self, 'ignore_lock_file', False):
            lines = self.generate_python_modules_from_lock_file()
            if lines:
                # override any existing lines with the python modules from the
                # lock file.
                existing_tactic = output_files.get('wheelhouse.txt')
                lock_layer = Layer('lockfile-wheelhouse',
                                   layers["layers"][-1].target_repo.dirname())
                lock_layer.directory = layers["layers"][-1].directory
                if existing_tactic is not None:
                    wheelhousetactic_class = existing_tactic.__class__
                else:
                    wheelhousetactic_class = WheelhouseTactic
                wh_tactic = wheelhousetactic_class(
                    "",
                    self.target,
                    lock_layer,
                    next_config,
                )
                wh_tactic.lines = lines
                wh_tactic.purge_wheels = False
                if existing_tactic is not None:
                    wh_tactic.combine(existing_tactic)
                output_files["wheelhouse.txt"] = wh_tactic

        if self.wheelhouse_overrides:
            existing_tactic = output_files.get('wheelhouse.txt')
            wh_over_layer = Layer('--wheelhouse-overrides',
                                  layers["layers"][-1].target_repo.dirname())
            wh_over_layer.directory = layers["layers"][-1].directory
            if existing_tactic is not None:
                wheelhousetactic_class = existing_tactic.__class__
            else:
                wheelhousetactic_class = WheelhouseTactic
            output_files['wheelhouse.txt'] = wheelhousetactic_class(
                self.wheelhouse_overrides,
                self.target,
                wh_over_layer,
                next_config,
            )
            output_files['wheelhouse.txt'].purge_wheels = True
            if existing_tactic is not None:
                output_files['wheelhouse.txt'].combine(existing_tactic)
        plan = [t for t in output_files.values() if t]
        return plan

    def plan_hooks(self, layers, output_files, plan):
        """
        Add a Tactic to the plan to handle rendering all standard hooks from
        the template, if not explicitly overridden.

        :param layers: Data structure containing all of the layers composing
            this charm, along with some overall metadata.
        :type layers: dict
        :param output_files: Mapping of file Paths to Tactics that should
            process those files.
        :type output_files: dict
        :param plan: List of all Tactics that need to be invoked.
        :type plan: list
        """
        if self.HOOK_TEMPLATE_FILE not in output_files:
            raise BuildError('At least one layer must provide %s',
                             self.HOOK_TEMPLATE_FILE)
        template_file = self.target.directory / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        source_layer = output_files[self.HOOK_TEMPLATE_FILE].layer
        plan.append(
            charmtools.build.tactics.StandardHooksBind(
                'hook', source_layer.url, self.target,
                target_config, output_files, template_file))

    def plan_interfaces(self, layers, output_files, plan):
        """
        Add Tactics to the plan for each relation endpoint to render hooks
        for that relation endpoint from the template, as well as a tactic
        to pull in the interface layer's code (if there is an interface layer).

        :param layers: Data structure containing all of the layers composing
            this charm, along with some overall metadata.
        :type layers: dict
        :param output_files: Mapping of file Paths to Tactics that should
            process those files.
        :type output_files: dict
        :param plan: List of all Tactics that need to be invoked.
        :type plan: list
        """
        # Interface includes don't directly map to output files
        # as they are computed in combination with the metadata.yaml
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

        template_file = path(self.target.directory) / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        specs = []
        used_interfaces = set()
        for role in ("provides", "requires", "peers"):
            for k, v in meta.get(role, {}).items():
                # ex: ["provides", "db", "mysql"]
                specs.append([role, k, v["interface"]])
                used_interfaces.add(v["interface"])

        for iface in layers.get("interfaces", []):
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
                         "" if iface.directory.startswith(self.cache_dir)
                         else " (from %s)" % iface.directory.relpath())
                # COPY phase
                plan.append(
                    charmtools.build.tactics.InterfaceCopy(
                        iface, relation_name, role,
                        self.target, target_config)
                )

        # Link Phase
        # owner = metadata_tactic[0].layer.url
        owner = output_files[self.HOOK_TEMPLATE_FILE].layer.url
        for role, relation_name, interface_name in specs:
            plan.append(charmtools.build.tactics.InterfaceBind(
                relation_name, owner, self.target,
                target_config, output_files, template_file))

    def plan_storage(self, layers, output_files, plan):
        """
        Add Tactics to the plan for each storage endpoint to render hooks
        for that storage endpoint from the template.

        :param layers: Data structure containing all of the layers composing
            this charm, along with some overall metadata.
        :type layers: dict
        :param output_files: Mapping of file Paths to Tactics that should
            process those files.
        :type output_files: dict
        :param plan: List of all Tactics that need to be invoked.
        :type plan: list
        """
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

        template_file = path(self.target.directory) / self.HOOK_TEMPLATE_FILE
        target_config = layers["layers"][-1].config
        for name, owner in meta_tac.storage.items():
            plan.append(
                charmtools.build.tactics.StorageBind(
                    name, owner, self.target,
                    target_config, output_files, template_file))

    def plan_version(self, layers, output_files, plan):
        plan.append(
            charmtools.build.tactics.VersionTactic(
                self.charm,
                self.target,
                self.top_layer, None,
            ))

    def formulate_plan(self, layers):
        """Build out a plan for each file in the various
        layers, taking into account config at each layer"""
        output_files = OrderedDict()
        self.plan = self.plan_layers(layers, output_files)
        self.plan_hooks(layers, output_files, self.plan)
        self.plan_interfaces(layers, output_files, self.plan)
        self.plan_storage(layers, output_files, self.plan)
        self.plan_version(layers, output_files, self.plan)
        return self.plan

    def post_metrics(self, kind, layer_name, fetched):
        if self.hide_metrics:
            return
        conf_file = path('~/.config/charm-build.conf').expanduser()
        try:
            conf = yaml.safe_load(conf_file.text()) or {}
        except (FileNotFoundError, yaml.error.YAMLError):
            conf = {}
        if not conf.get('cid'):
            conf_file.parent.makedirs_p()
            conf['cid'] = str(uuid.uuid4())
            conf_file.write_text(yaml.safe_dump(conf))
        cid = conf['cid']
        try:
            requests.post(self.METRICS_URL, timeout=10, data={
                'tid': self.METRICS_ID,
                'v': 1,
                'aip': 1,
                't': 'event',
                'ds': 'app',
                'cid': cid,
                'av': format_version(cached_charm_tools_version(), 'long'),
                'an': "charm-build",
                'ec': kind,
                'ea': 'fetch' if fetched else 'local',
                'el': layer_name,
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
                    if hasattr(tactic, "lock_info"):
                        self.lock_items.extend(tactic.lock_info)
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
        if getattr(self, 'write_lock_file', False):
            self.write_the_lock_file()
        if self.report:
            self.write_report(new_repo, added, changed, removed)

    def write_signatures(self, signatures, layers):
        signatures['.build.manifest'] = ["build", 'dynamic', 'unchecked']
        self.manifest.write_text(json.dumps(dict(
            signatures=signatures,
            layers=layers,
        ), indent=2, sort_keys=True))

    def write_the_lock_file(self):
        """Using the info in self.layers, write a lock file.

        The lock file can be used to ensure that the same versions (or
        branches) are used to recreate the charm.
        """
        locks = []
        # look at the layers first for locks
        for layer in self.layers:
            branch = layer.get('branch', None)
            if branch is None or branch == 'refs/heads/master':
                tag = layer.get('rev', None)
            else:
                tag = branch
            lock_item = {
                'type': 'layer',
                'item': layer['url'],
                'url': layer.get('fetched_url', None),
                'vcs': layer.get('vcs', None),
                'branch': branch,
                'commit': tag
            }
            locks.append(lock_item)
        # now iterate through the other lock items and add them in
        locks.extend(self.lock_items)
        self.lock_file.write_text(json.dumps({'locks': locks}, indent=2))

    def maybe_read_lock_file(self):
        """Read the lock file if it exists.

        The lock file is a list of elements (either layer, interface or python
        module).  This is then used in the fetcher system to fix the versions
        that are used when rebuilding the charm.
        """
        self.with_locks = {}
        if (getattr(self, 'ignore_lock_file', False) or
                getattr(self, 'write_lock_file', False)):
            return
        try:
            with open(self.lock_file) as f:
                with_locks = json.load(f)
        except FileNotFoundError:
            log.info("The lockfile %s was not found; building using latest "
                     "versions.", self.lock_file)
            return
        except Exception as err:
            log.error("Problem decoding the lock file: %s\n%s",
                      self.lock_file, str(err))
            raise
        # re-format the lock-file as a dictionary so that the items can be
        # looked up.  A layer is 'layer:<name>', an interface is
        # 'interface:<name>', and a python moudle is 'python_module:<name>'
        for item in with_locks['locks']:
            if item['type'] == 'python_module':
                self.with_locks["python_module:{}".format(item['package'])] = \
                    item
            elif item['type'] == 'layer':
                self.with_locks[item['item']] = item
            else:
                log.warning("Not sure how to deal with lock item '%s'?", item)
        log.info("Using lockfile %s for build.", self.lock_file)

    def generate_python_modules_from_lock_file(self):
        """Using self.with_locks[], generate a list of python module lines.

        This takes the python modules recorded in the lock file, as read into
        self.with_locks[] and generate a list of python module line in the
        style of a requiremens.txt file suitable for pip.  These are absolute
        version locks (or github commit/branch locks).

        :returns: list of python module lines
        :rtype: List[str]
        """
        lines = []
        for data in self.with_locks.values():
            if data['type'] != "python_module":
                continue
            vcs = data['vcs']
            if vcs == 'git':
                if self.use_lock_file_branches:
                    branch = data.get('branch', '')
                    if branch.startswith("refs/heads/"):
                        branch = branch[len("refs/heads/"):]
                    line = "{}@{}#egg={}".format(
                        data['url'], branch, data['package'])
                else:
                    line = "{}@{}#egg={}".format(
                        data['url'], data['version'], data['package'])
            elif vcs is None:
                line = "{}=={}".format(data['package'], data['version'])
            else:
                log.error("Unknown vcs type %s - aborting.", vcs)
                sys.exit(1)
            lines.append(line)
        return lines

    def generate(self):
        layers = self.fetch()
        self.formulate_plan(layers)
        self.exec_plan(self.plan, self.layers)

    def validate(self):
        if not (self.name and str(self.name)[0] in string.ascii_lowercase):
            raise BuildError('Charm name must start with a lower-case letter')

        for cls in (InterfaceFetcher, LayerFetcher):
            if cls.OLD_ENVIRON in os.environ and cls.ENVIRON not in os.environ:
                log.warning('DEPRECATED: {} environment variable; '
                            'please use {} instead'.format(cls.OLD_ENVIRON,
                                                           cls.ENVIRON))

        self._validate_charm_repo()

        if not self.manifest.exists():
            return [], [], []
        a, c, d = utils.delta_signatures(self.manifest, ignore=DEFAULT_IGNORES)

        for f in a:
            log.warn("Conflict: File in destination directory "
                     "was added after charm build: %s", f)
        for f in c:
            log.warn("Conflict: File in destination directory "
                     "was modified after charm build: %s", f)
        for f in d:
            log.warn("Conflict: File in destination directory "
                     "was deleted after charm build: %s", f)
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

    def create_charm_file(self):
        dst_name = '{}.charm'.format(self.name)
        with ZipFile(dst_name, 'w', ZIP_DEFLATED) as zip:
            for src_path in self.target_dir.walkfiles():
                zip.write(src_path, src_path.relpath(self.target_dir))

    def __call__(self):
        log.debug(json.dumps(
            self.status(), indent=2, sort_keys=True, default=str))
        self.validate()
        self.find_or_create_target()
        self.generate()
        if self.charm_file:
            self.create_charm_file()
        self.cleanup()

    def inspect(self):
        self.charm = path(self.charm).abspath()
        self._check_path(self.charm)
        inspector.inspect(self.charm,
                          force_styling=self.force_color,
                          annotate=self.annotate)

    def normalize_build_dir(self):
        charm_build_dir = os.environ.get('CHARM_BUILD_DIR')
        juju_repo_dir = os.environ.get('JUJU_REPOSITORY')
        series = self.series or 'builds'
        if not self.build_dir:
            if self.output_dir:
                self.build_dir = self.output_dir
            elif charm_build_dir:
                self.build_dir = path(charm_build_dir)
            elif juju_repo_dir:
                self.build_dir = path(juju_repo_dir) / series
            else:
                log.warn('Build dir not specified via command-line or '
                         'environment; defaulting to /tmp/charm-builds')
                self.build_dir = path('/tmp/charm-builds')
        self.build_dir = self.build_dir.abspath()
        charm_dir = path(self.charm).abspath() + os.path.sep
        if os.path.commonprefix([self.build_dir, charm_dir]) == charm_dir:
            raise BuildError('Build directory nested under source directory. '
                             'This will cause recursive nesting of build '
                             'artifacts and can fill up your disk. Please '
                             'specify a different build directory with '
                             '--build-dir or $CHARM_BUILD_DIR')

    def normalize_cache_dir(self):
        charm_cache_dir = os.environ.get('CHARM_CACHE_DIR')
        if not self.cache_dir:
            if charm_cache_dir:
                self.cache_dir = path(charm_cache_dir)
            else:
                self.cache_dir = path('~/.cache/charm').expanduser()
        self.cache_dir = self.cache_dir.abspath() / str(os.getpid())
        if self.cache_dir.startswith(path(self.charm).abspath()):
            raise BuildError('Cache directory nested under source directory. '
                             'This will cause recursive nesting of build '
                             'artifacts and can fill up your disk. Please '
                             'specify a different build directory with '
                             '--cache-dir or $CHARM_CACHE_DIR')

    def _check_path(self, path_to_check, need_write=False, can_create=False):
        if not path_to_check:
            return
        if not os.path.exists(path_to_check):
            if not can_create:
                raise BuildError('Missing required path: '
                                 '{}'.format(path_to_check))
            try:
                path_to_check.makedirs_p()
            except Exception:
                raise BuildError('Unable to create required path: '
                                 '{}'.format(path_to_check))
        if not os.access(path_to_check, os.R_OK):
            raise BuildError('Unable to read from: {}'.format(path_to_check))
        if need_write and not os.access(path_to_check, os.W_OK):
            raise BuildError('Unable to write to: {}'.format(path_to_check))

    def check_paths(self):
        self._check_path(self.build_dir, need_write=True, can_create=True)
        self._check_path(self.cache_dir, need_write=True, can_create=True)
        self._check_path(self.wheelhouse_overrides)

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

    def cleanup(self):
        log.debug('Cleaning up {}'.format(self.cache_dir))
        self.cache_dir.rmtree_p()


def make_url_from_lock_for_layer(lock_spec, use_branches=False):
    """Make a url from a lock spec for a layer or interface.

    lock_spec is:

    "layer:basic": {
      "branch": "refs/heads/master",
      "commit": "623e69c7b432456fd4364f6e1835424fd6b5425e",
      "item": "layer:basic",
      "type": "layer",
      "url": "https://github.com/juju-solutions/layer-basic.git",
      "vcs": null
    }

    If the 'item' is present, then use that, so that the correct LayerFetcher
    or InterfaceFetcher will be used.  Otherwise, It is assumed that the VCS is
    git.

    The result will be in the form <item>@<branch|commit> or
    <url>@<branch|item> depending on whether the item is present and the
    use_branches is True.

    :param lock_spec: the lock specification for the layer
    :type lock_spec: Dict[str, Dict[str, Optional[str]]]
    :param use_branches: if True, use the branch, rather than the commit
    :type use_branches: bool
    :returns: the url for fetching the layer from the repository
    :rtype: str
    """
    try:
        url = lock_spec["item"]
    except KeyError:
        url = lock_spec["url"]
    if use_branches:
        branch = lock_spec["branch"]
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]
        return "{}@{}".format(url, branch)
    else:
        return "{}@{}".format(url, lock_spec["commit"])


def configLogging(build):
    global log
    logging.captureWarnings(True)
    term = os.environ.get('TERM')
    if term and term.startswith('screen.'):
        term = term[7:]
    record_format = '%(name)s: %(message)s'
    try:
        clifmt = utils.ColoredFormatter(
            blessings.Terminal(term, force_styling=build.force_color),
            record_format)
    except curses.error:
        try:
            # try falling back to basic term type
            clifmt = utils.ColoredFormatter(
                blessings.Terminal('linux', force_styling=build.force_color),
                record_format)
        except curses.error:
            # fall back to uncolored formatter
            clifmt = logging.Formatter(record_format)
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
        description='inspect the layers of a built charm. This '
                    'renders a tree of the files in the color '
                    'of each layer. Each layers assigned color '
                    'is presented in a legend at the top of the '
                    'output.')
    parser.add_argument('-r', '--force-raw', action="store_true",
                        dest='force_color', help="Alias of --force-color")
    parser.add_argument('-c', '--force-color', action="store_true",
                        help="Force raw output (color)")
    parser.add_argument('-a', '--annotate', action="store_true",
                        help="Annotate each file with the layer name, "
                             "rather than just using colors "
                             "(this is enabled automatically enabled if "
                             "colors are unavailable)")
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('charm', nargs="?", default=".", type=path)
    utils.add_plugin_description(parser)
    # Namespace will set the options as attrs of build
    parser.parse_args(args, namespace=build)
    configLogging(build)
    try:
        build.inspect()
    except BuildError as e:
        if e.args:
            log.error(*e.args)
        raise SystemExit(1)


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
    env_vars = (
        ("CHARM_LAYERS_DIR", "Directory containing local copies of base "
                             "layers"),
        ("CHARM_INTERFACES_DIR", "Directory containing local copies of "
                                 "interface layers"),
        ("CHARM_BUILD_DIR", "Build charms will be placed into "
                            "$CHARM_BUILD_DIR/{charm_name} "
                            "(defaults to /tmp/charm-builds/)"),
        ("JUJU_REPOSITORY", "Deprecated: If CHARM_BUILD_DIR is not set but "
                            "this is, built charms will be placed into "
                            "$JUJU_REPOSITORY/builds/{charm_name}"),
        ("LAYER_PATH", "Deprecated: Alias of CHARM_LAYERS_DIR"),
        ("INTERFACE_PATH", "Deprecated: Alias of CHARM_INTERFACES_DIR"),
    )
    build = Builder()
    parser = argparse.ArgumentParser(
        description="build a charm from layers and interfaces",
        epilog="The following environment variables will be honored:\n" +
               "\n" +
               "".join("  {:<20}  {}\n".format(name, desc)
                       for name, desc in env_vars),
        formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-f', '--force', action="store_true")
    parser.add_argument('-o', '--output-dir', type=path,
                        help='Alias for --build-dir')
    parser.add_argument('-d', '--build-dir', type=path,
                        help='Directory under which to place built charms; '
                             'overrides CHARM_BUILD_DIR env')
    parser.add_argument('-C', '--cache-dir', type=path,
                        help='Directory to cache build dependencies '
                        '(default: ~/.cache/charm; can also be set via '
                        'CHARM_CACHE_DIR env)')
    parser.add_argument('-s', '--series', default=None,
                        help='Deprecated: define series in metadata.yaml')
    parser.add_argument('--hide-metrics', dest="hide_metrics",
                        action="store_true")
    parser.add_argument('--interface-service',
                        help="Deprecated: use --layer-index")
    parser.add_argument('-i', '--layer-index',
                        help='One or more index URLs used to look up layers, '
                             'separated by commas. Can include the token '
                             'DEFAULT, which will be replaced by the default '
                             'index{} ({}).  E.g.: '
                             'https://my-site.com/index/,DEFAULT'.format(
                                 'es' if len(LayerFetcher.LAYER_INDEXES) > 1
                                 else '',
                                 ','.join(LayerFetcher.LAYER_INDEXES)))
    parser.add_argument('--no-local-layers', action="store_true",
                        help="Don't use local layers when building. "
                        "Forces included layers to be downloaded "
                        "from the interface service.")
    parser.add_argument('-n', '--name',
                        help="Build a charm of 'name' from 'charm'")
    parser.add_argument('--write-lock-file', action="store_true",
                        default=False,
                        help="Write a lock file for reproducible builds. The "
                             "file is 'layers.lock' in the root of the layer "
                             "being build.")
    parser.add_argument('--use-lock-file-branches', action="store_true",
                        default=False,
                        help="Use branch names if not master branch in "
                             "lockfile. This allows tracking of a stable "
                             "branch.")
    parser.add_argument('--ignore-lock-file', action="store_true",
                        default=False,
                        help="Ignore the lock file even if it is present.")
    parser.add_argument('-r', '--report', action="store_true", default=True,
                        help="Show post-build report of changes")
    parser.add_argument('-R', '--no-report', action="store_false",
                        dest='report', default=True,
                        help="Don't show post-build report of changes")
    parser.add_argument('-w', '--wheelhouse-overrides', type=path,
                        help="Provide a wheelhouse.txt file with overrides "
                             "for the built wheelhouse")
    parser.add_argument('-W', '--wheelhouse-per-layer', action="store_true",
                        help="Deprecated: Use original wheelhouse processing "
                             "method (see PR juju/charm-tools#569)")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Increase output (same as -l DEBUG)")
    parser.add_argument('--debug', action='store_true',
                        help='Same as --log-level=DEBUG')
    parser.add_argument('-c', '--force-color', action="store_true",
                        help="Force raw output (color)")
    parser.add_argument('--charm-file', '-F', action='store_true',
                        help='Create a .charm file in the current directory')
    parser.add_argument('charm', nargs="?", default=".", type=path,
                        help='Source directory for charm layer to build '
                             '(default: .)')
    utils.add_plugin_description(parser)
    # Namespace will set the options as attrs of build
    parser.parse_args(args, namespace=build)
    if build.charm == "help":
        parser.print_help()
        raise SystemExit(0)

    if build.verbose or build.debug:
        build.log_level = logging.DEBUG

    LayerFetcher.set_layer_indexes(build.interface_service or
                                   build.layer_index)
    LayerFetcher.NO_LOCAL_LAYERS = build.no_local_layers

    WheelhouseTactic.per_layer = build.wheelhouse_per_layer

    configLogging(build)

    try:
        build.check_series()
        build.normalize_build_dir()
        build.normalize_cache_dir()
        build.check_paths()
        build.maybe_read_lock_file()

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

        if exit_code > 0:
            raise SystemExit(exit_code)

    except (BuildError, FetchError) as e:
        log.debug(traceback.format_exc())
        if e.args:
            log.error(*e.args)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
