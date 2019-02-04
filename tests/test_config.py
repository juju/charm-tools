import logging
import os
import unittest

from charmtools.build.config import BuildConfig


class TestConfig(unittest.TestCase):
    def test_rget(self):
        c = BuildConfig()
        c['a'] = 1
        c = c.new_child()
        c['a'] = 99
        c['b'] = "alpha"
        self.assertEqual(c.get('a'), 99)
        self.assertEqual(c.get('b'), "alpha")
        self.assertEqual(c.rget('a'), [99, 1])

    def test_tactics(self):
        # configure from empty and a layer with tactics
        c = BuildConfig()
        c._tactics = ['a', 'b', 'c']
        c = c.new_child()
        c._tactics = ['d', 'c']
        self.assertEqual(c.tactics[:5], ['d', 'c', 'a', 'b', 'c'])

    def test_utf8(self):
        """ Test that utf8 characters in the layer config work."""
        del os.environ['LANG']
        c = BuildConfig()
        c.configure("tests/layers/utf8-layer/interface.yaml")


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
