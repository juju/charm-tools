# Tests for Python charm helpers.

from simplejson import dumps
from testtools import TestCase

import charmhelpers


class CharmHelpersTestCase(TestCase):
    """A basic test case for Python charm helpers."""


    def test_get_config(self):
        # get_config returns the contents of the current charm
        # configuration, as returned by config-get --format=json.
        mock_config = {'key': 'value'}

        # Monkey-patch shelltoolbox.command to avoid having to call out
        # to config-get. This nesting of lambdas is a bit horrible
        # because get_config() defines its own config_get() command, but
        # since it's not used anywhere else this is preferable to making
        # config_get() a global.
        config_get_cmd = lambda *args: lambda: dumps(mock_config)
        self.patch(charmhelpers, 'command', config_get_cmd)

        self.assertEqual(mock_config, charmhelpers.get_config())
