from __future__ import print_function

import unittest
from unittest import TestCase
from charmtools import utils
from six import StringIO


class TestUtils(TestCase):

    def test_delta_python(self):
        a = StringIO("""
        def foo(n):
            return n * 2


        @when('db.ready')
        def react(db):
            print(db)
        """)

        b = StringIO("""
        def foo(n):
            return n * 2


        @when('db.ready', 'bar')
        def react(db):
            print(db)
        """)

        result = StringIO()
        t = utils.TermWriter(fp=result)
        rc = utils.delta_python_dump(a, b, utils.REACTIVE_PATTERNS,
                                     context=3,
                                     term=t,
                                     from_name="Alpha",
                                     to_name="Beta")
        # return code here indicates that there was a diff
        self.assertFalse(rc)
        result.seek(0)
        output = result.read()
        self.assertIn("Alpha", output)
        self.assertIn("Beta", output)
        self.assertIn("@when('db.ready'", output)
        self.assertIn("bar", output)

    @unittest.mock.patch("os.environ")
    def test_host_env(self, mock_environ):
        mock_environ.copy.return_value = {
            'PREFIX': 'fake-prefix',
            'PYTHONHOME': 'fake-pythonhome',
            'PYTHONPATH': 'fake-pythonpath',
            'GIT_TEMPLATE_DIR': 'fake-git-template-dir',
            'GIT_EXEC_PATH': 'fake-git-exec-path',
            'SOME_OTHER_KEY': 'fake-some-other-key',
            'PATH': '/snap/charm/current/bin:/usr/bin:'
                    '/snap/charm/current/usr/bin:/bin',
        }
        self.assertDictEqual(
            {'SOME_OTHER_KEY': 'fake-some-other-key', 'PATH': '/usr/bin:/bin'},
            utils.host_env())

    @unittest.mock.patch.object(utils, "Process")
    def test_pin_setuptools_for_pep440(self, mock_Process):
        utils.pin_setuptools_for_pep440('/some/dir', env={'some': 'envvar'})
        mock_Process.assert_called_once_with(
            ('/some/dir/bin/pip', 'install', '-U', 'pip<23.1',
             'setuptools<67'),
            env={'some': 'envvar'})
