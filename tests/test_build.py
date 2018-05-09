#!usr/bin/env python2
import os
import json
import unittest
import logging
import pkg_resources
from path import Path as path


from charmtools import build
from charmtools.build.errors import BuildError
from charmtools import utils
from path import Path as path
from ruamel import yaml
import mock
import responses


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.dirname = path(pkg_resources.resource_filename(__name__, ""))
        os.environ["LAYER_PATH"] = self.dirname
        os.environ["INTERFACE_PATH"] = self.dirname / "interfaces"
        path("out").rmtree_p()
        self.p_post = mock.patch('requests.post')
        self.p_post.start()

    def tearDown(self):
        path("out").rmtree_p()
        self.p_post.stop()

    def test_invalid_layer(self):
        """Test that invalid metadata.yaml files get a BuildError exception."""
        builder = build.Builder()
        builder.log_level = "DEBUG"
        builder.output_dir = "out"
        builder.series = "trusty"
        builder.name = "invalid-charm"
        builder.charm = "trusty/invalid-layer"
        metadata = path("tests/trusty/invalid-layer/metadata.yaml")
        try:
            builder()
            self.fail('Expected Builder to throw an exception on invalid YAML')
        except BuildError as e:
            self.assertEqual(
                "Failed to process {0}. "
                "Ensure the YAML is valid".format(metadata.abspath()), str(e))

    def test_tester_layer(self):
        bu = build.Builder()
        bu.log_level = "WARNING"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/tester"
        bu.hide_metrics = True
        bu.report = False
        remove_layer_file = self.dirname / 'trusty/tester/to_remove'
        remove_layer_file.touch()
        self.addCleanup(remove_layer_file.remove_p)
        with mock.patch.object(build.builder, 'log') as log:
            bu()
            log.warn.assert_called_with(
                'Please add a `repo` key to your layer.yaml, '
                'with a url from which your layer can be cloned.')
        base = path('out/trusty/foo')
        self.assertTrue(base.exists())

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
        actions = yaml.load((base / "actions.yaml").text())
        resources = yaml.load((base / "resources.yaml").text())
        self.assertNotIn("test-base", actions)
        self.assertIn("mysql", actions)
        self.assertIn("tester", actions)
        self.assertIn("test-base", resources)
        self.assertNotIn("mysql", resources)
        self.assertIn("tester", resources)

        # Metadata should have combined provides fields
        metadata = base / "metadata.yaml"
        self.assertTrue(metadata.exists())
        metadata_data = yaml.load(metadata.open())
        self.assertIn("shared-db", metadata_data['provides'])
        self.assertIn("storage", metadata_data['provides'])
        # The maintainer, maintainers values should only be from the top layer.
        self.assertIn("maintainer", metadata_data)
        self.assertEqual(metadata_data['maintainer'], "Tester <test@er.com>")
        self.assertNotIn("maintainers", metadata_data)
        # The tags list must be de-duplicated.
        self.assertEqual(metadata_data['tags'], ["databases"])
        self.assertEqual(metadata_data['series'], ['xenial', 'trusty'])

        # Config should have keys but not the ones in deletes
        config = base / "config.yaml"
        self.assertTrue(config.exists())
        config_data = yaml.load(config.open())['options']
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
        cyaml_data = yaml.load(cyaml.open())
        self.assertEquals(cyaml_data['includes'], ['trusty/test-base',
                                                   'trusty/mysql'])
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
            u'03fc06a5e698e624231b826f4c47a60d3251cbc968fc1183ada444ca09b29ea6'
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
        bu()
        self.assertFalse((base / 'to_remove').exists())

    def test_regenerate_inplace(self):
        # take a generated example where a base layer has changed
        # regenerate in place
        # make some assertions
        bu = build.Builder()
        bu.log_level = "WARNING"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/b"
        bu.hide_metrics = True
        bu.report = False
        bu()
        base = path('out/trusty/foo')
        self.assertTrue(base.exists())

        # verify the 1st gen worked
        self.assertTrue((base / "a").exists())
        self.assertTrue((base / "README.md").exists())

        # now regenerate from the target
        with utils.cd("out/trusty/foo"):
            bu = build.Builder()
            bu.log_level = "WARNING"
            bu.output_dir = path(os.getcwd())
            bu.series = "trusty"
            # The generate target and source are now the same
            bu.name = "foo"
            bu.charm = "."
            bu.hide_metrics = True
            bu.report = False
            bu()
            base = bu.output_dir
            self.assertTrue(base.exists())

            # Check that the generated layer.yaml makes sense
            cy = base / "layer.yaml"
            config = yaml.load(cy.open())
            self.assertEquals(config["includes"], ["trusty/a", "interface:mysql"])
            self.assertEquals(config["is"], "foo")

            # We can even run it more than once
            bu()
            cy = base / "layer.yaml"
            config = yaml.load(cy.open())
            self.assertEquals(config["includes"], ["trusty/a", "interface:mysql"])
            self.assertEquals(config["is"], "foo")

            # We included an interface, we should be able to assert things about it
            # in its final form as well
            provides = base / "hooks/relations/mysql/provides.py"
            requires = base / "hooks/relations/mysql/requires.py"
            self.assertTrue(provides.exists())
            self.assertTrue(requires.exists())

            # and that we generated the hooks themselves
            for kind in ["joined", "changed", "broken", "departed"]:
                self.assertTrue((base / "hooks" /
                                 "mysql-relation-{}".format(kind)).exists())

            # and ensure we have an init file (the interface doesn't its added)
            init = base / "hooks/relations/mysql/__init__.py"
            self.assertTrue(init.exists())

    @responses.activate
    def test_remote_interface(self):
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
        bu.log_level = "WARNING"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/c-reactive"
        bu.hide_metrics = True
        bu.report = False
        bu()
        base = path('out/trusty/foo')
        self.assertTrue(base.exists())

        # basics
        self.assertTrue((base / "a").exists())
        self.assertTrue((base / "README.md").exists())
        # show that we pulled the interface from github
        init = base / "hooks/relations/pgsql/__init__.py"
        self.assertTrue(init.exists())
        main = base / "hooks/reactive/main.py"
        self.assertTrue(main.exists())

    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    @responses.activate
    def test_remote_layer(self, mcall, ph):
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
        bu.log_level = "WARNING"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/use-layers"
        bu.hide_metrics = True
        bu.report = False
        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]

        bu()
        base = path('out/trusty/foo')
        self.assertTrue(base.exists())

        # basics
        self.assertTrue((base / "README.md").exists())

        # show that we pulled charmhelpers from the basic layer as well
        mcall.assert_called_with(("pip3", "install",
                                  "--user", "--ignore-installed",
                                  mock.ANY), env=mock.ANY)

    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("charmtools.utils.Process")
    def test_pypi_installer(self, mcall, ph):
        bu = build.Builder()
        bu.log_level = "WARN"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/chlayer"
        bu.hide_metrics = True
        bu.report = False

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        bu()
        mcall.assert_called_with(("pip3", "install",
                                  "--user", "--ignore-installed",
                                  mock.ANY), env=mock.ANY)

    @mock.patch("charmtools.build.builder.Builder.plan_hooks")
    @mock.patch("path.Path.rmtree_p")
    @mock.patch("tempfile.mkdtemp")
    @mock.patch("charmtools.utils.Process")
    def test_wheelhouse(self, Process, mkdtemp, rmtree_p, ph):
        mkdtemp.return_value = '/tmp'
        bu = build.Builder()
        bu.log_level = "WARN"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/whlayer"
        bu.hide_metrics = True
        bu.report = False
        bu.wheelhouse_overrides = self.dirname / 'wh-over.txt'

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with mock.patch("path.Path.mkdir_p"):
            with mock.patch("path.Path.files"):
                bu()
                Process.assert_any_call((
                    'bash', '-c', '. /tmp/bin/activate ;'
                    ' pip3 download --no-binary :all: '
                    '-d /tmp -r ' +
                    self.dirname / 'trusty/whlayer/wheelhouse.txt'))
                Process.assert_any_call((
                    'bash', '-c', '. /tmp/bin/activate ;'
                    ' pip3 download --no-binary :all: '
                    '-d /tmp -r ' +
                    self.dirname / 'wh-over.txt'))

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


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
