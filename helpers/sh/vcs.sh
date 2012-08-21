#!/bin/bash

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
# URL Match patterns
CH_VCS_BZR_URL_PATTERN="^(lp:\~|bzr:\/\/|bzr+ssh:\/\/)"
CH_VCS_GIT_URL_PATTERN="(^git@|^git:\/\/|\.git$)"
CH_VCS_SVN_URL_PATTERN="^(svn:\/\/|svn+ssh:\/\/)"
CH_VCS_HG_URL_PATTERN="" #UGH, they only have ssh:// and https?:// SO DIFFICULT.
# This is a VERY generous pattern and should weed out the majority of malformed URLS
CH_VCS_VALID_URL_PATTERN="(lp:|(https?|svn|bzr|git|ssh)(\+ssh)?://)[-A-z0-9\+&@#/%?=~_|!:,.;]*[-A-z0-9\+&@#/%=~_|]"

##
# File Match patterns
CH_VCS_BZR_FILE=".bzr"
CH_VCS_GIT_FILE=".git"
CH_VCS_SVN_FILE=".svn"
CH_VCS_HG_FILE=".hg"

##
# Detect VCS
# Try to determine the Source Control tool used
#
# param URL - URL of remote source
#
# echo type|null
##
ch_detect_vcs()
{
	REPO_URL=${1:-""}

	if [ -z "$REPO_URL" ]; then
		return 1
	fi

}

##
# Fetch Repo
# Pull down the repository and return it's temporary path
# param REPO_URL - URL of the remote source
# param REPO_TYPE optional - The type of VCS to use
#
# echo path|null
#
# return 0 OK
# return 1 No REPO_URL
# return 2 Not a valid URL
##
ch_fetch_repo()
{
	local REPO_URL=${1:-""}
	local REPO_TYPE=${2:-""}

	if [ -z "$REPO_URL" ]; then
		# Don't give me crap!
		return 1
	fi

	if [ -z "$REPO_TYPE" ]; then
		# FUUUU, got to go figure it out now
		# Assume nothing, this could be garbage.
		if [[ $REPO_URL =~ $CH_VCS_VALID_URL_PATTERN ]]; then
			# Do magic?
		else
			return 2
		fi
	fi
}

##
# Update Repository
# This will "update" the repository to the latest rev
#
# param REPO_PATH - The local path to the repository
#
# echo null
#
# return 0 OK
# return 1 No REPO_PATH
# return 2 Not a valid path
# return 3 Could not determine repository type
##
ch_update_repo()
{
	local REPO_PATH=${1:-""}

	if [ ! -d "$REPO_PATH" ]; then
		return 1
	fi
}
