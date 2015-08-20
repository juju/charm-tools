import unittest
from charmtools.generate import (
    graph,
    copy_file,
)
from mock import patch


class JujuCharmAddTest(unittest.TestCase):
    @patch('charmtools.generate.Charms')
    def test_graph(self, mcharm):
        m = mcharm.return_value
        m.search.return_value = [{'foo': 'bar'}]
        self.assertEqual(graph('nagios', 'requires'), {'foo': 'bar'})
        m.search.assert_called_with({'series': 'trusty',
                                     'provides': 'nagios'})

    @patch('charmtools.generate.Charms')
    def test_graph_no_interface(self, mcharm):
        m = mcharm.return_value
        m.search.return_value = None
        self.assertEqual(graph('nointerface', 'requires'), None)
        m.search.assert_called_with({'series': 'trusty',
                                     'provides': 'nointerface'})

    @patch('charmtools.generate.Charm')
    def test_not_charm(self, mcharm):
        mcharm.return_value.is_charm.return_value = False
        self.assertRaises(Exception, copy_file, '1.ex', '/no-charm')
