#!/usr/bin/python

#    Copyright (C) 2013  Canonical Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import unittest

from mock import Mock
from charmtools.promulgate import get_lp_charm_series


class NotFound(Exception):
    content = None
    def __init__(self, content):
        self.content = content


class TestCharmProof(unittest.TestCase):
    def test_get_lp_charm_series(self):
        lp = Mock()
        charms = Mock()
        charms.getSeries.return_value = "trusty"
        lp.distributions = {'charms': charms}
        self.assertEqual('trusty', get_lp_charm_series(lp, 'trusty'))

    def test_get_lp_charm_series_none(self):
        lp = Mock()
        charms = Mock()
        charms.getSeries.return_value = "trusty"
        lp.distributions = {'charms': charms}
        self.assertRaises(ValueError, get_lp_charm_series, lp, None)

    def test_get_lp_charm_series_404(self):
        lp = Mock()
        charms = Mock()
        charms.getSeries.side_effect = NotFound('No such distribution series:')
        lp.distributions = {'charms': charms}
        self.assertRaises(NotFound, get_lp_charm_series, lp, 'not-series')
