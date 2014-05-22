#!/usr/bin/python

#    Copyright (C) 2014  Canonical Ltd.
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


class Prompt(object):
    def __init__(self, name, text, default):
        self.name = name
        self.text = text
        self.default = default

    def validate(self, value):
        """Return the (possibly modified) validated value, or raise ValueError
        with a message explaining why the value is invalid.

        """
        return value
