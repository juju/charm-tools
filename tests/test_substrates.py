"""Unit test for juju tests substrate handling"""

import unittest
import yaml
from charmtools.test import parse_substrates, allowed_substrates


class JujuTestSubstrateTests(unittest.TestCase):
    INCLUDE_SKIP = '''
substrates:
    order: include, skip
    skip: amazon
    include: "*"
    '''

    SKIP_INCLUDE = '''
substrates:
    order: skip, include
    skip: "*"
    include: amazon
    '''

    def test_parse_substrates_text(self):
        self.assertRaises(ValueError,  parse_substrates, '')
        self.assertIsNotNone(parse_substrates(self.INCLUDE_SKIP))

    def test_parse_substrate_dict(self):
        data = yaml.safe_load(self.INCLUDE_SKIP)
        self.assertIsNotNone(parse_substrates(data))

    def test_parse_substrate_object(self):
        class Object(object):
            pass
        data = yaml.safe_load(self.INCLUDE_SKIP)
        o = Object()
        o.__dict__ = data
        self.assertIsNotNone(parse_substrates(o))

    def test_parse_substrates_order(self):
        result = parse_substrates(self.INCLUDE_SKIP)
        self.assertEqual(result.order, ['include', 'skip'])

    def test_parse_substrates_order_invalid(self):
        data = self.INCLUDE_SKIP.replace('skip', 'foobar')
        self.assertRaises(ValueError, parse_substrates, data)

    def test_parse_substrates_include(self):
        result = parse_substrates(self.INCLUDE_SKIP)
        self.assertEqual(result.include, set(['*']))

    def test_parse_substrates_skip(self):
        result = parse_substrates(self.INCLUDE_SKIP)
        self.assertEqual(result.skip, set(['amazon']))

    def test_filter_include_skip(self):
        rules = parse_substrates(self.INCLUDE_SKIP)
        self.assertEqual(rules.filter('amazon,hp,azure'), ['azure', 'hp'])

    def test_filter_skip_include(self):
        rules = parse_substrates(self.SKIP_INCLUDE)
        self.assertEqual(rules.filter('amazon,hp,azure'), ['amazon'])

    def test_allowed_substrates(self):
        self.assertEqual(allowed_substrates(self.INCLUDE_SKIP,
                                            ['foo', 'bar', 'amazon']),
                         ['bar', 'foo'])


if __name__ == '__main__':
    unittest.main()
