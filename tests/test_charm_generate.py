import unittest
from charmtools.generate import graph
from mock import patch


class JujuCharmAddTest(unittest.TestCase):
    @patch('charmtools.generate.Charms')
    def test_graph(self, mcharm):
        m = mcharm.return_value
        m.search.return_value = [{'foo': 'bar'}]
        self.assertEqual(graph('nagios', 'requires'), {'foo': 'bar'})
        m.search.assert_called_with({'series': 'precise',
                                     'provides': 'nagios'})

    @patch('charmtools.generate.Charms')
    def test_graph_no_interface(self, mcharm):
        m = mcharm.return_value
        m.search.return_value = None
        self.assertEqual(graph('nointerface', 'requires'), None)
        m.search.assert_called_with({'series': 'precise',
                                     'provides': 'nointerface'})
