#!/bin/sh

##
# Copyright: 2012 Marco Ceppi <marco@ceppi.net>
# Copyright: Copyright 2011, Canonical Ltd., All Rights Reserved.
#
# This file is part of Charm Helpers.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
	echo "${1%%/*}"
}

##
# ch_service_name <unit>
# Alias of ch_unit_name
#
# returns <service> | FALSE
ch_service_name()
{
	echo "`ch_unit_name $1`"
}

##
# ch_unit_id <unit-name>
# Returns the unit id
#
# Param <unit-name> is the name of the unit
#
# returns <unit-d> | FALSE
ch_unit_id()
{
    echo "${1##*/}"
}

##
# ch_my_unit_id
# Returns the unit id of the current unit
#
# param none
#
# returns <unit-id> | FALSE
ch_my_unit_id()
{
    echo "`ch_unit_id $JUJU_UNIT_NAME`"
}
