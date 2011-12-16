#!/bin/sh

#Copyright: Copyright 2011, Canonical Ltd., All Rights Reserved.
#License: GPL-3
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# .
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# .
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

##
# ch_peer_i_am_leader
# Returns 1 if the current unit is the leader
#
# no params
#
# return 0|1
ch_peer_i_am_leader()
{
    local REMOTE_UNIT_ID=`ch_unit_id $JUJU_REMOTE_UNIT`
    local LOCAL_UNIT_ID=`ch_my_unit_id`
    local FIRST_UNIT=`relation-list | head -n 1`
    local FIRST_UNIT_ID=`ch_unit_id $FIRST_UNIT`

    if [ $LOCAL_UNIT_ID -lt $REMOTE_UNIT_ID ] && [ $LOCAL_UNIT_ID -lt $FIRST_UNIT_ID ]; then
        return 0
    else
        return 1
    fi
} 

##
# ch_peer_leader [--id]
#
# Return the name [or id] of the leader unit
#
# Option --id will have the function return the unit id instead
#
# Returns leader-unit-name[or ID]
ch_peer_leader()
{
    if ch_peer_i_am_leader; then
        # this is the leader, return our own unit name
        local leader="$JUJU_UNIT_NAME"
    else
        # this is  a slave the leader is the head of the list
        local leader="`relation-list | head -n 1`"
    fi
    if [ $# -gt 0 ] && [ "$1" = "--id" ]; then
        echo "`ch_unit_id $leader`"
    else
        echo "$leader"
    fi
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
