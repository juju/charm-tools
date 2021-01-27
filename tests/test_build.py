#!usr/bin/env python2
import os
import json
import unittest
import logging
import pkg_resources
import zipfile
from path import Path as path, TempDir


from charmtools import build
from charmtools.build.errors import BuildError
from ruamel import yaml
import mock
import responses


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.dirname = path(pkg_resources.resource_filename(__name__, ""))
        self.build_dir = TempDir()
        os.environ["CHARM_HIDE_METRICS"] = 'true'
        os.environ["CHARM_LAYERS_DIR"] = self.dirname / "layers"
        os.environ["CHARM_INTERFACES_DIR"] = self.dirname / "interfaces"
        os.environ["CHARM_CACHE_DIR"] = self.build_dir / "_cache"
        os.environ.pop("JUJU_REPOSITORY", None)
        os.environ.pop("LAYER_PATH", None)
        os.environ.pop("INTERFACE_PATH", None)
        self.p_post = mock.patch('requests.post')
        self.p_post.start()

    def tearDown(self):
        self.build_dir.rmtree_p()
        self.p_post.stop()
        build.fetchers.LayerFetcher.restore_layer_indexes()

    def test_default_no_hide_metrics(self):
        # In the absence of environment variables or command-line options,
        # Builder.hide_metrics is false.
        os.environ.pop("CHARM_HIDE_METRICS", None)
        builder = build.Builder()
        self.assertFalse(builder.hide_metrics)

    def test_environment_hide_metrics(self):
        # Setting the environment variable CHARM_HIDE_METRICS to a non-empty
        # value causes Builder.hide_metrics to be true.
        os.environ["CHARM_HIDE_METRICS"] = 'true'
        builder = build.Builder()
        self.assertTrue(builder.hide_metrics)

    def test_invalid_layer(self):
        # Test that invalid metadata.yaml files get a BuildError exception.
        builder = build.Builder()
        builder.log_level = "DEBUG"
        builder.build_dir = self.build_dir
        builder.cache_dir = builder.build_dir / "_cache"
        builder.series = "trusty"
        builder.name = "invalid-charm"
        builder.charm = "layers/invalid-layer"
        builder.no_local_layers = False
        metadata = path("tests/layers/invalid-layer/metadata.yaml")
        try:
            with self.dirname:
                builder()
            self.fail('Expected Builder to throw an exception on invalid YAML')
        except BuildError as e:
            self.assertEqual(
                "Failed to process {0}. "
                "Ensure the YAML is valid".format(metadata.abspath()), str(e))

    @mock.patch("argparse.ArgumentParser.parse_args")
    @mock.patch("charmtools.build.builder.proof")
    @mock.patch("charmtools.build.builder.Builder")
    def test_failed_proof(self, mBuilder, mproof, mparse_args):
        # Test that charm-proof failures get a BuildError exception.
        mproof.proof.return_value = ([], 200)
        mBuilder().charm_file = False
        try:
            build.builder.main()
            self.fail('Expected Builder to throw an exception on proof error')
        except SystemExit as e:
            self.assertEqual(e.code, 200)

    @mock.patch("charmtools.build.builder.Builder.plan_version")
    def test_tester_layer(self, pv):
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARNING"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/tester"
        bu.hide_metrics = True
        bu.report = False
        bu.charm_file = True
        remove_layer_file = self.dirname / 'layers/tester/to_remove'
        remove_layer_file.touch()
        charm_file = self.dirname / 'foo.charm'
        self.addCleanup(remove_layer_file.remove_p)
        self.addCleanup(charm_file.remove_p)
        with self.dirname:
            with mock.patch.object(build.builder, 'log') as log:
                with mock.patch.object(build.builder, 'repofinder') as rf:
                    rf.get_recommended_repo.return_value = None
                    bu()
                    log.warn.assert_called_with(
                        'Please add a `repo` key to your layer.yaml, '
                        'with a url from which your layer can be cloned.')
                    log.warn.reset_mock()
                    rf.get_recommended_repo.return_value = 'myrepo'
                    bu()
                    log.warn.assert_called_with(
                        'Please add a `repo` key to your layer.yaml, '
                        'e.g. repo: myrepo')
        base = bu.target_dir
        self.assertTrue(base.exists())
        self.assertTrue(charm_file.exists())
        with zipfile.ZipFile(charm_file, 'r') as zip:
            assert 'metadata.yaml' in zip.namelist()

        # Confirm that copyright file of lower layers gets renamed
        # and copyright file of top layer doesn't get renamed
        tester_copyright = (base / "copyright").text()
        mysql_copyright_path = base / "copyright.layer-mysql"
        self.assertIn("Copyright of tester", tester_copyright)
        self.assertTrue(mysql_copyright_path.isfile())

        # Verify ignore rules applied
        self.assertFalse((base / ".bzr").exists())
        self.assertEqual((base / "ignore").text(), "mysql\n")
        self.assertEqual((base / "exclude").text(), "test-base\n")
        self.assertEqual((base / "override-ignore").text(), "tester\n")
        self.assertEqual((base / "override-exclude").text(), "tester\n")
        self.assertFalse((base / "tests/00-setup").exists())
        self.assertFalse((base / "tests/15-configs").exists())
        self.assertTrue((base / "tests/20-deploy").exists())
        actions = yaml.safe_load((base / "actions.yaml").text())
        resources = yaml.safe_load((base / "resources.yaml").text())
        self.assertNotIn("test-base", actions)
        self.assertIn("mysql", actions)
        self.assertIn("tester", actions)
        self.assertIn("test-base", resources)
        self.assertNotIn("mysql", resources)
        self.assertIn("tester", resources)

        # Metadata should have combined provides fields
        metadata = base / "metadata.yaml"
        self.assertTrue(metadata.exists())
        metadata_data = yaml.safe_load(metadata.open())
        self.assertIn("shared-db", metadata_data['provides'])
        self.assertIn("storage", metadata_data['provides'])
        # The maintainer, maintainers values should only be from the top layer.
        self.assertIn("maintainer", metadata_data)
        self.assertEqual(metadata_data['maintainer'],
                         b"T\xc3\xa9sty T\xc3\xa9st\xc3\xa9r "
                         b"<t\xc3\xa9st\xc3\xa9r@example.com>".decode('utf8'))
        self.assertNotIn("maintainers", metadata_data)
        # The tags list must be de-duplicated.
        self.assertEqual(metadata_data['tags'], ["databases"])
        self.assertEqual(metadata_data['series'], ['xenial', 'trusty'])

        # Config should have keys but not the ones in deletes
        config = base / "config.yaml"
        self.assertTrue(config.exists())
        config_data = yaml.safe_load(config.open())['options']
        self.assertIn("bind-address", config_data)
        self.assertNotIn("vip", config_data)
        self.assertIn("key", config_data)
        self.assertEqual(config_data["key"]["default"], None)
        # Issue #99 where strings lose their quotes in a charm build.
        self.assertIn("numeric-string", config_data)
        default_value = config_data['numeric-string']['default']
        self.assertEqual(default_value, "0123456789", "value must be a string")
        # Issue 218, ensure proper order of layer application
        self.assertEqual(config_data['backup_retention_count']['default'], 7,
                         'Config from layers was merged in wrong order')

        cyaml = base / "layer.yaml"
        self.assertTrue(cyaml.exists())
        cyaml_data = yaml.safe_load(cyaml.open())
        self.assertEquals(cyaml_data['includes'], ['layers/test-base',
                                                   'layers/mysql'])
        self.assertEquals(cyaml_data['is'], 'foo')
        self.assertEquals(cyaml_data['options']['mysql']['qux'], 'one')

        self.assertTrue((base / "hooks/config-changed").exists())

        # Files from the top layer as overrides
        start = base / "hooks/start"
        self.assertTrue(start.exists())
        self.assertIn("Overridden", start.text())

        # Standard hooks generated from template
        stop = base / "hooks/stop"
        self.assertTrue(stop.exists())
        self.assertIn("Hook: ", stop.text())

        self.assertTrue((base / "README.md").exists())
        self.assertEqual("dynamic tactics", (base / "README.md").text())

        self.assertTrue((base / "old_tactic").exists())
        self.assertEqual("processed", (base / "old_tactic").text())

        sigs = base / ".build.manifest"
        self.assertTrue(sigs.exists())
        data = json.load(sigs.open())
        self.assertEquals(data['signatures']["README.md"], [
            u'foo',
            "static",
            u'cfac20374288c097975e9f25a0d7c81783acdbc81'
            '24302ff4a731a4aea10de99'])

        self.assertEquals(data["signatures"]['metadata.yaml'], [
            u'foo',
            "dynamic",
            u'12c1f6fc865da0660f6dc044cca03b0244e883d9a99fdbdfab6ef6fc2fed63b7'
            ])

        storage_attached = base / "hooks/data-storage-attached"
        storage_detaching = base / "hooks/data-storage-detaching"
        self.assertTrue(storage_attached.exists())
        self.assertTrue(storage_detaching.exists())
        self.assertIn("Hook: data", storage_attached.text())
        self.assertIn("Hook: data", storage_detaching.text())

        # confirm that files removed from a base layer get cleaned up
        self.assertTrue((base / 'to_remove').exists())
        remove_layer_file.remove()
        with self.dirname:
            bu()
        self.assertFalse((base / 'to_remove').exists())

    @mock.patch("charmtools.build.builder.Builder.plan_version")
    @responses.activate
    def test_remote_interface(self, pv):
        # XXX: this test does pull the git repo in the response
        responses.add(responses.GET,
                      "https://juju.github.io/layer-index/"
                      "interfaces/pgsql.json",
                      body='''{
                      "id": "pgsql",
                      "name": "pgsql4",
                      "repo":
                      "https://github.com/bcsaller/juju-relation-pgsql.git",
                      "summary": "Postgres interface"
                      }''',
                      content_type="application/json")
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARNING"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/c-reactive"
        bu.hide_metrics = True
        bu.report = False
        with self.dirname:
            bu()
        base = bu.target_dir
        self.assertTrue(base.exists())

        # basics
        self.assertTrue((base / "a").exists())
        self.assertTrue((base / "README.md").exists())
        # show that we pulled the interface from github
        init = base / "hooks/relations/pgsql/__init__.py"
        self.assertTrue(init.exists())
        main = base / "hooks/reactive/main.py"
        self.assertTrue(main.exists())

    @mock.patch("charmtools.build.builder.Builder.plan_version")
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    @responses.activate
    def test_remote_layer(self, mcall, ph, pi, pv):
        # XXX: this test does pull the git repo in the response
        responses.add(responses.GET,
                      "https://juju.github.io/layer-index/"
                      "layers/basic.json",
                      body='''{
                      "id": "basic",
                      "name": "basic",
                      "repo":
                      "https://git.launchpad.net/~bcsaller/charms/+source/basic",
                      "summary": "Base layer for all charms"
                      }''',
                      content_type="application/json")
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARNING"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/use-layers"
        bu.hide_metrics = True
        bu.report = False
        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]

        with self.dirname:
            bu()
        base = bu.target_dir
        self.assertTrue(base.exists())

        # basics
        self.assertTrue((base / "README.md").exists())

        # show that we pulled charmhelpers from the basic layer as well
        mcall.assert_called_with(("pip3", "install",
                                  "--user", "--ignore-installed",
                                  mock.ANY), env=mock.ANY)

    @mock.patch("charmtools.build.builder.Builder.plan_version")
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    def test_pypi_installer(self, mcall, ph, pi, pv):
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARN"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/chlayer"
        bu.hide_metrics = True
        bu.report = False

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with self.dirname:
            bu()
        mcall.assert_called_with(("pip3", "install",
                                  "--user", "--ignore-installed",
                                  mock.ANY), env=mock.ANY)

    @mock.patch(
        "charmtools.build.tactics.VersionTactic._try_to_get_current_sha",
        return_value="fake sha")
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    def test_version_tactic_without_existing_version_file(self, mcall, ph, pi,
                                                          get_sha):
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARN"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/chlayer"
        bu.hide_metrics = True
        bu.report = False

        # ensure no an existing version file
        version_file = bu.charm / 'version'
        version_file.remove_p()

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with self.dirname:
            bu()

        self.assertEqual((bu.target_dir / 'version').text(), 'fake sha')

    @mock.patch("charmtools.build.tactics.VersionTactic.CMDS", (
        ('does_not_exist_cmd', ''),
    ))
    @mock.patch("charmtools.build.tactics.InstallerTactic.trigger",
                classmethod(lambda *a: False))
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    def test_version_tactic_missing_cmd(self, ph, pi):
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARN"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/chlayer"
        bu.hide_metrics = True
        bu.report = False

        # ensure no an existing version file
        version_file = bu.charm / 'version'
        version_file.remove_p()

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with self.dirname:
            bu()

        assert not (bu.target_dir / 'version').exists()

    @mock.patch("charmtools.build.tactics.VersionTactic.read",
                return_value="sha1")
    @mock.patch(
        "charmtools.build.tactics.VersionTactic._try_to_get_current_sha",
        return_value="sha2")
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    def test_version_tactic_with_existing_version_file(self, mcall, ph, pi,
                                                       get_sha, read):
        bu = build.Builder()
        bu.ignore_lock_file = True
        bu.log_level = "WARN"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "layers/chlayer"
        bu.hide_metrics = True
        bu.report = False

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with self.dirname:
            with mock.patch.object(build.tactics, 'log') as log:
                bu()
                log.warn.assert_has_calls(
                    [mock.call('version sha1 is out of update, '
                               'new sha sha2 will be used!')],
                    any_order=True)

        self.assertEqual((bu.target_dir / 'version').text(), 'sha2')

    @mock.patch("charmtools.utils.sign")
    @mock.patch("charmtools.build.builder.Builder.plan_version")
    @mock.patch("charmtools.build.builder.Builder.plan_interfaces")
    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("path.Path.rmtree_p")
    @mock.patch("tempfile.mkdtemp")
    @mock.patch("charmtools.utils.Process")
    def test_wheelhouse(self, Process, mkdtemp, rmtree_p, ph, pi, pv, sign):
        build.tactics.WheelhouseTactic.per_layer = False
        mkdtemp.return_value = '/tmp'
        bu = build.Builder()
        bu.log_level = "WARN"
        bu.build_dir = self.build_dir
        bu.cache_dir = bu.build_dir / "_cache"
        bu.series = "trusty"
        bu.name = "whlayer"
        bu.charm = "layers/whlayer"
        bu.hide_metrics = True
        bu.report = False
        bu.wheelhouse_overrides = self.dirname / 'wh-over.txt'

        def _store_wheelhouses(args):
            filename = args[-1].split()[-1]
            if filename.endswith('.txt'):
                Process._wheelhouses.append(path(filename).lines(retain=False))
            return mock.Mock(return_value=mock.Mock(exit_code=0))
        Process._wheelhouses = []
        Process.side_effect = _store_wheelhouses

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with self.dirname:
            with mock.patch("path.Path.mkdir_p"):
                with mock.patch("path.Path.files"):
                    bu()
                    self.assertEqual(len(Process._wheelhouses), 1)
                    # note that setuptools uses both hyphen and underscore, but
                    # that should be normalized so that they match
                    self.assertEqual(Process._wheelhouses[0], [
                        '# layers/whbase',
                        '# base-comment',
                        '# foo==1.0  # overridden by whlayer',
                        '# bar==1.0  # overridden by whlayer',
                        '# qux==1.0  # overridden by whlayer',
                        '# setuptools-scm<=1.17.0  # overridden by '
                        '--wheelhouse-overrides',
                        '',
                        '# whlayer',
                        '# git+https://github.com/me/baz#egg=baz  # comment',
                        'foo==2.0',
                        'git+https://github.com/me/bar#egg=bar',
                        '# qux==2.0  # overridden by --wheelhouse-overrides',
                        '',
                        '# --wheelhouse-overrides',
                        'git+https://github.com/me/qux#egg=qux',
                        'setuptools_scm>=3.0<=3.4.1',
                        '',
                    ])

        sign.return_value = 'signature'
        wh = build.tactics.WheelhouseTactic(path('wheelhouse.txt'),
                                            mock.Mock(directory=path('wh')),
                                            mock.Mock(url='charm'),
                                            mock.Mock())
        # package name gets normalized properly when checking _layer_refs
        wh._layer_refs['setuptools-scm'] = 'layer:foo'
        wh.tracked = {path('wh/setuptools_scm-1.17.0.tar.gz')}
        self.assertEqual(wh.sign(), {
            'wheelhouse.txt': ('charm',
                               'dynamic',
                               'signature'),
            'setuptools_scm-1.17.0.tar.gz': ('layer:foo',
                                             'dynamic',
                                             'signature'),
        })

    @mock.patch.object(build.tactics, 'path')
    def test_wheelhouse_missing_package_name(self, path):
        wh = build.tactics.WheelhouseTactic(mock.Mock(name='entity'),
                                            mock.Mock(name='target'),
                                            mock.Mock(name='layer', url='foo'),
                                            mock.Mock(name='next_config'))
        path().text.return_value = 'https://example.com/my-package'
        with self.assertRaises(BuildError):
            wh.read()
        path().text.return_value = 'https://example.com/my-package#egg=foo'
        wh.read()
        self.assertIn('foo', wh._layer_refs.keys())

    @mock.patch.object(build.tactics, 'log')
    @mock.patch.object(build.tactics.YAMLTactic, 'read',
                       lambda s: setattr(s, '_read', True))
    def test_layer_options(self, log):
        entity = mock.MagicMock(name='entity')
        target = mock.MagicMock(name='target')
        config = mock.MagicMock(name='config')

        base_layer = mock.MagicMock(name='base_layer')
        base_layer.directory.name = 'layer-base'
        base_layer.name = 'base'
        base = build.tactics.LayerYAML(entity, target, base_layer, config)
        base.data = {
            'defines': {
                'foo': {
                    'type': 'string',
                    'default': 'FOO',
                    'description': "Don't set me, bro",
                },
                'bar': {
                    'enum': ['yes', 'no'],
                    'description': 'Go to the bar?',
                },
            }
        }
        assert base.lint()
        self.assertEqual(base.data['options']['base']['foo'], 'FOO')

        top_layer = mock.MagicMock(name='top_layer')
        top_layer.directory.name = 'layer-top'
        top_layer.name = 'top'
        top = build.tactics.LayerYAML(entity, target, top_layer, config)
        top.data = {
            'options': {
            },
            'defines': {
                'qux': {
                    'type': 'boolean',
                    'default': False,
                    'description': "Don't set me, bro",
                },
            }
        }
        assert top.lint()
        top.data['options'].update({
            'base': {
                'bar': 'bah',
            }
        })
        assert not top.lint()
        top.combine(base)
        assert not top.lint()
        log.error.assert_called_with('Invalid value for option %s: %s',
                                     'base.bar',
                                     "'bah' is not one of ['yes', 'no']")
        log.error.reset_mock()
        top.data['options']['base']['bar'] = 'yes'
        assert top.lint()
        self.assertEqual(top.data['options'], {
            'base': {
                'foo': 'FOO',
                'bar': 'yes',
            },
            'top': {
                'qux': False,
            },
        })

    @mock.patch('charmtools.build.tactics.getargspec')
    @mock.patch('charmtools.utils.walk')
    def test_custom_tactics(self, mwalk, mgetargspec):
        def _layer(tactics):
            return mock.Mock(config=build.builder.BuildConfig({'tactics':
                                                               tactics}),
                             directory=path('.'),
                             url=tactics[0])

        builder = build.builder.Builder()
        builder.ignore_lock_file = True
        builder.build_dir = self.build_dir
        builder.cache_dir = builder.build_dir / "_cache"
        builder.charm = 'foo'
        layers = {'layers': [
            _layer(['first']),
            _layer(['second']),
            _layer(['third']),
        ]}

        builder.plan_layers(layers, {})
        calls = [call[1]['current_config'].tactics
                 for call in mwalk.call_args_list]
        self.assertEquals(calls, [
            ['first'],
            ['second', 'first'],
            ['third', 'second', 'first'],
        ])

        mgetargspec.return_value = mock.Mock(args=[1, 2, 3, 4])
        current_config = mock.Mock(tactics=[
            mock.Mock(name='1', **{'trigger.return_value': False}),
            mock.Mock(name='2', **{'trigger.return_value': False}),
            mock.Mock(name='3', **{'trigger.return_value': True}),
        ])
        build.tactics.Tactic.get(mock.Mock(),
                                 mock.Mock(),
                                 mock.Mock(),
                                 mock.Mock(),
                                 current_config,
                                 mock.Mock())
        self.assertEquals([t.trigger.called for t in current_config.tactics],
                          [True, True, True])
        self.assertEquals([t.called for t in current_config.tactics],
                          [False, False, True])


class TestFetchers(unittest.TestCase):
    @mock.patch.object(build.fetchers, 'get_fetcher')
    def test_get_repo_fetcher_target(self, get_fetcher):
        f = get_fetcher()
        f.repo = '/home/user/deps/foo/trunk'
        fetcher = build.fetchers.InterfaceFetcher('interface:foo')
        result = fetcher._get_repo_fetcher_and_target('repo', '/dir_')
        self.assertEqual(result, (f, '/dir_/foo'))

    @mock.patch('charmtools.build.fetchers.RepoFetcher.can_fetch',
                mock.Mock(return_value=False))
    @mock.patch('charmtools.build.fetchers.InterfaceFetcher.NO_LOCAL_LAYERS',
                True)
    @mock.patch('tempfile.mkdtemp', mock.Mock(return_value='/tmp/src'))
    @mock.patch('charmtools.fetchers.git')
    @mock.patch('charmtools.build.fetchers.path.rmtree_p', mock.Mock())
    @mock.patch('charmtools.build.fetchers.shutil.copytree')
    @mock.patch('charmtools.build.fetchers.requests')
    def test_subdir(self, requests, copytree, git):
        requests.get.return_value.ok = True
        requests.get.return_value.json.return_value = {
            'repo': 'https://github.com/juju-solutions/mock-repo',
            'subdir': 'layers/test',
        }
        fetcher = build.fetchers.get_fetcher('layer:test')
        assert fetcher
        assert fetcher.subdir == 'layers/test'
        target = fetcher.fetch('/tmp/dst')
        self.assertEqual(target, '/tmp/dst/test')
        copytree.assert_called_once_with(path('/tmp/src/layers/test'),
                                         path('/tmp/dst/test'))


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
