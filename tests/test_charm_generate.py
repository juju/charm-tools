import unittest
from charmtools.generate import (
    graph,
    copy_file,
)
from mock import patch, Mock


class JujuCharmAddTest(unittest.TestCase):
    @patch('charmtools.generate.CharmStore')
    def test_graph(self, store):
        charm = Mock(series='trusty')
        store = store.return_value
        store.provides.return_value = [charm]
        self.assertEqual(graph('nagios', 'requires'), charm)
        store.provides.assert_called_with('nagios')

    @patch('charmtools.generate.CharmStore')
    def test_graph_no_interface(self, store):
        store = store.return_value
        store.provides.return_value = []
        self.assertEqual(graph('nointerface', 'requires'), None)
        store.provides.assert_called_with('nointerface')

    @patch('charmtools.generate.Charm')
    def test_not_charm(self, mcharm):
        mcharm.return_value.is_charm.return_value = False
        self.assertRaises(Exception, copy_file, '1.ex', '/no-charm')
