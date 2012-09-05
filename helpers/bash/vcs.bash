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

CH_VCS_INSTALL_DEPS=${CH_VCS_INSTALL_DEPS:-"true"}

##
# URL Match patterns
CH_VCS_BZR_URL_PATTERN="^(lp:~?|bzr:|bzr\+ssh:)"
CH_VCS_GIT_URL_PATTERN="(^git@|^git:|.git$)"
CH_VCS_SVN_URL_PATTERN="^(svn:|svn\+ssh:)"
CH_VCS_HG_URL_PATTERN="" #UGH, they only have ssh:// and https?:// SO DIFFICULT.
# This is a VERY generous pattern and should weed out the majority of malformed URLS
# Not sure why this didn't work. It works with `egrep -E`, but whatever.
#CH_VCS_VALID_URL_PATTERN="(lp:|(https?|svn|bzr|git|ssh)(+ssh)?://)[-a-z0-9+&/?=_:.]*[-a-z0-9+&/=_]"
CH_VCS_VALID_URL_PATTERN="^(lp:~?|https?://|svn://|svn\+ssh://|bzr://|bzr\+ssh://|git://|ssh://)[-a-z0-9\+&/?=_:.@]+*[-a-z0-9\+&/=_]"

##
# "clone", "branch", "fetch" commands
CH_VCS_BZR_FETCH_CMD="branch"
CH_VCS_GIT_FETCH_CMD="clone"
CH_VCS_SVN_FETCH_CMD="co"
CH_VCS_HG_FETCH_CMD="clone"

##
# "pull", "up", updated commands
CH_VCS_BZR_UPDATE_CMD="pull"
CH_VCS_GIT_UPDATE_CMD="pull"
CH_VCS_SVN_UPDATE_CMD="up"
CH_VCS_HG_UPDATE_CMD="pull"

##
# File Match patterns
CH_VCS_BZR_FILE=".bzr"
CH_VCS_GIT_FILE=".git"
CH_VCS_SVN_FILE=".svn"
CH_VCS_HG_FILE=".hg"

##
# Supported VCS
CH_VCS_SUPPORTED_TYPES=( bzr git svn hg )

##
# Make sure all requirements are fullfiled
if [ "$CH_VCS_INSTALL_DEPS" = "true" ]; then
	apt-get install -y subversion git-core bzr mercurial
fi

##
# Detect VCS
# Try to determine the Source Control tool used
#
# param URL - URL of remote source
#
# echo type|null
#
# return 0 OK
# return 1 No REPO_URL
# return 2 Not a valid VCS
##
ch_detect_vcs()
{
	local REPO_URL=${1:-""}

	if [ -z "$REPO_URL" ]; then
		return 1
	fi

	if [ -d "$REPO_URL" ]; then
		# This is no URL! It's a path!
		# Go through each repo type and find out which one we have
		for type in "${CH_VCS_SUPPORTED_TYPES[@]}"; do
			local REPO_FILE="CH_VCS_${type^^}_FILE"
			local REPO_FILE="${!REPO_FILE}"

			if [ -d $REPO_URL/$REPO_FILE ]; then
				echo $type
				return 0
			fi
		done

		# It's a directory, but we couldn't match a VCS tool. We should bail
		# because I _doubt_ it'll be a URL.
		return 2
	fi
	# So, it's not a local path? Okay, maybe it's a URL?

	# This should be a loop
	if [[ $REPO_URL =~ $CH_VCS_BZR_URL_PATTERN ]]; then
		# It's a BZR repo!
		echo "bzr"
		return 0
	elif [[ $REPO_URL =~ $CH_VCS_GIT_URL_PATTERN ]]; then
		# It's a Git repo!
		echo "git"
		return 0
	elif [[ $REPO_URL =~ $CH_VCS_SVN_URL_PATTERN ]]; then
		# It's subversion!
		echo "svn"
		return 0
	elif [[ "$REPO_URL" =~ $CH_VCS_VALID_URL_PATTERN ]]; then
		for type in "${CH_VCS_SUPPORTED_TYPES[@]}"; do
			local TMP_REPO=`ch_fetch_repo "$REPO_URL" "$type"`
			local TMP_RESULT=$?
			if [ $TMP_RESULT -eq 0 ]; then
				# It's $type! Clean up and bail
				rm -rf $TMP_REPO
				echo "$type"
				return 0
			elif [ $TMP_RESULT -le 2 ]; then
				# Something went wrong, and it shouldn't have.
				return 128
			fi

			rm -rf "$TMP_REPO"
		done
	fi

	return 2 # Not a valid VCS system
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
# return 3 Unable to fetch
##
ch_fetch_repo()
{
	local REPO_URL=${1:-""}
	local REPO_TYPE=${2:-""}

	# Check for crap
	if [ -z "$REPO_URL" ]; then
		# Don't give me crap!
		return 1
	fi

	# If we're guessing, then lets guess!
	if [ -z "$REPO_TYPE" ]; then
		# FUUUU, got to go figure it out now
		# Assume nothing, this could be garbage.
		if [[ $REPO_URL =~ $CH_VCS_VALID_URL_PATTERN ]]; then
			local REPO_TYPE=`ch_detect_vcs $REPO_URL`

			if [ $? -gt 0 ] || [ -z "$REPO_TYPE" ]; then
				return 2
			fi
		else
			return 2
		fi
	fi

	local REPO_FETCH_CMD="CH_VCS_${REPO_TYPE^^}_FETCH_CMD"
	local REPO_FETCH_CMD="${!REPO_FETCH_CMD}"

	local REPO_PATH=`mktemp -d /tmp/charm-helper-vcs-$REPO_TYPE.XXXXXX`
	local REPO_OPTS=""

	# CURE YOU BZR!!!!!
	if [ $REPO_TYPE == "bzr" ]; then
		REPO_OPTS="--use-existing-dir"
	fi
		

	$REPO_TYPE $REPO_FETCH_CMD $REPO_OPTS $REPO_URL $REPO_PATH > /dev/null 2>&1

	if [ $? -ne 0 ]; then
		rm -rf $REPO_PATH
		return 3
	fi

	echo $REPO_PATH
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
# return 2 Not a valid repo path
# return 3 Failed to update repo
##
ch_update_repo()
{
	local REPO_PATH=${1:-""}

	if [ ! -d "$REPO_PATH" ]; then
		return 1
	fi

	REPO_TYPE=`ch_detect_vcs "$REPO_PATH"`

	if [ $? -ne 0 ]; then
		return 3
	fi

	local REPO_UPDATE="CH_VCS_${REPO_TYPE^^}_UPDATE_CMD"
	local REPO_UPDATE="${!REPO_UPDATE}"
	local CWD=`pwd`

	cd $REPO_PATH
	$REPO_TYPE $REPO_UPDATE > /dev/null 2>&1
	local SUCC=$?
	cd $CWD

	if [ $SUCC -eq 0 ]; then
		return 0
	else
		return 3
	fi

	return 2
}
