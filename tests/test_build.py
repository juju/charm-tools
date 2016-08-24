from charmtools import build
from charmtools.build.errors import BuildError
from charmtools import utils
from path import path
from ruamel import yaml
import json
import logging
import mock
import os
import pkg_resources
import responses
import unittest


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.dirname = path(pkg_resources.resource_filename(__name__, ""))
        os.environ["LAYER_PATH"] = self.dirname
        os.environ["INTERFACE_PATH"] = self.dirname / "interfaces"
        path("out").rmtree_p()

    def tearDown(self):
        path("out").rmtree_p()

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

        self.assertTrue((base / "README.md").exists())
        self.assertEqual("dynamic tactics", (base / "README.md").text())

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
            u'5691b0c0aaf43d0f27d8eca6afbd1145aa3f4307456757e592827f002cf603f2'
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
                      "http://interfaces.juju.solutions/api/v1/interface/pgsql/",
                      body='''{
                      "id": "pgsql",
                      "name": "pgsql4",
                      "repo":
                      "https://github.com/bcsaller/juju-relation-pgsql.git",
                      "_id": {
                          "$oid": "55a471959c1d246feae487e5"
                      },
                      "version": 1
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

    @mock.patch("charmtools.utils.Process")
    @responses.activate
    def test_remote_layer(self, mcall):
        # XXX: this test does pull the git repo in the response
        responses.add(responses.GET,
                      "http://interfaces.juju.solutions/api/v1/layer/basic/",
                      body='''{
                      "id": "basic",
                      "name": "basic",
                      "repo":
                      "https://git.launchpad.net/~bcsaller/charms/+source/basic",
                      "_id": {
                          "$oid": "55a471959c1d246feae487e5"
                      },
                      "version": 1
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

    @mock.patch("charmtools.utils.Process")
    def test_pypi_installer(self, mcall):
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

    @mock.patch("path.Path.rmtree_p")
    @mock.patch("tempfile.mkdtemp")
    @mock.patch("charmtools.utils.Process")
    def test_wheelhouse(self, Process, mkdtemp, rmtree_p):
        mkdtemp.return_value = '/tmp'
        bu = build.Builder()
        bu.log_level = "WARN"
        bu.output_dir = "out"
        bu.series = "trusty"
        bu.name = "foo"
        bu.charm = "trusty/whlayer"
        bu.hide_metrics = True
        bu.report = False

        # remove the sign phase
        bu.PHASES = bu.PHASES[:-2]
        with mock.patch("path.Path.mkdir_p"):
            with mock.patch("path.Path.files"):
                bu()
                Process.assert_called_with((
                    '/tmp/bin/pip3', 'install',
                    '--no-binary', ':all:',
                    '-d', '/tmp',
                    '-r', self.dirname / 'trusty/whlayer/wheelhouse.txt'))

    @mock.patch.object(build.tactics, 'log')
    @mock.patch.object(build.tactics.YAMLTactic, 'read',
                       lambda s: setattr(s, '_read', True))
    def test_layer_options(self, log):
        entity = mock.MagicMock(name='entity')
        target = mock.MagicMock(name='target')
        config = mock.MagicMock(name='config')

        base_layer = mock.MagicMock(name='base_layer')
        base_layer.directory.name = 'base'
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
        top_layer.directory.name = 'top'
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


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
