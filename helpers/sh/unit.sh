#!/bin/sh

##
# Copyright 2012 Marco Ceppi <marco@ceppi.net>
#
# This file is part of Charm Helpers.
#
# Charm Helpers is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Charm Helpers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Charm Helpers.  If not, see <http://www.gnu.org/licenses/>.
##

##
# ch_unit_name <unit>
# Returns the unit (service) name
#
# Param <unit> is the name of the unit
#
# returns <service> | FALSE
ch_unit_name()
{
	return "${1%%/*}"
}

##
# ch_service_name <unit>
# Alias of ch_unit_name
#
# returns <service> | FALSE
ch_service_name()
{
	return ch_unit_name "$1"
}
