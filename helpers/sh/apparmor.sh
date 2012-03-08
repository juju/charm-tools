#!/bin/sh

##
# Copyright 2011 Canonical, Ltd. All Rights Reserved
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

ch_apparmor_load() {
    local ddir=${CH_APPARMOR_DESTDIR:-""}
    [ -n "$CHARM_DIR" ] || return 1
    [ -d "$CHARM_DIR" ] || return 1
    [ -d "$CHARM_DIR/apparmor/profiles.d" ] || return 0
    cp -f $CHARM_DIR/apparmor/profiles.d/* $ddir/etc/apparmor.d || return 1
    service apparmor reload || return 0
    return 0
}
