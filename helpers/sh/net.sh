#!/bin/sh

##
# Copyright 2011 Marco Ceppi <marco@ceppi.net>
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
# Globally overridable settings. Make sure to set them before sourcing
# this file.
CH_WGET_ARGS=${CH_WGET_ARGS:-"-q --content-disposition"}

##
# Get File
# Retrives a file and compares the file to a hash
#
# param FILE URL or Path to file
# param HASH URL, Path, or HASH string for file's hash
#
# return filepath|null
##
ch_get_file()
{
	local FILE=${1:-""}
	local HASH=${2:-""}
	local CH_DOWNLOAD_DIR=${CH_DOWNLOAD_DIR:-"`mktemp -d /tmp/ch-downloads.XXXXXX`"}

	if [ `ch_is_url "$FILE"` ]; then
		wget $CH_WGET_ARGS --directory-prefix="$CH_DOWNLOAD_DIR/" "$FILE"
		FILE=$CH_DOWNLOAD_DIR/$(ls -tr $CH_DOWNLOAD_DIR|head -n 1)
	fi

	if [ ! -f "$FILE" ]; then
		return 2
	fi

	if [ -z "$HASH" ];then
		#echo "Warning, no has specified. The file will be downloaded but not cryptographically checked!" > 2
		echo "$FILE"
		return 0
	elif [ `ch_is_url "$HASH"` ]; then
		local HASHNAME=$(basename $HASH)
		wget $CH_WGET_ARGS "$HASH" -O /tmp/$HASHNAME
		HASH=$(cat /tmp/$HASHNAME | awk '{ print $1 }')
	elif [ -f "$HASH" ]; then
		HASH=$(cat "$HASH" | awk '{ print $1 }')
	fi

	local HASH_TYPE=$(ch_type_hash $HASH)

	if [ -z "$HASH_TYPE" ]; then
		return 3
	else
		local FILE_HASH=$(${HASH_TYPE}sum $FILE | awk '{ print $1 }')

		if [ "$FILE_HASH" != "$HASH" ]; then
			return 4
		fi
	fi

	echo "$FILE"
	return 0
}

##
# Hash Type
# Determine, using best approximation, if the hash is valid and what type
# of hashing algorithm was used
#
# param HASH
#
# return type|false
##
ch_type_hash()
{
	local DIRTY="$1"

	case $DIRTY in
		*[![:xdigit:]]* | "" )
			echo ""
			return 1
		;;
		* )
			case ${#DIRTY} in
				32 )
					echo md5
				;;
				40 )
					echo sha1
				;;
				64 )
					echo sha256
				;;
			esac
		;;
	esac
}

##
# Is URL?
# Checks if the string passed is a valid URL (http(s), ftp)
#
# param URL The URL to be checked
#
# return boolean
##
ch_is_url()
{
	local DIRTY="$1"

	case "$DIRTY" in
		"http://"* | "https://"* | "ftp://"*)
			echo true
			return 0
		;;
		*)
			return 1
		;;
	esac
}

##
# Is IP?
# Checks if the string passed is an IP address
#
# param IP The IP addressed to be checked
#
# return boolean
##
ch_is_ip()
{
	local DIRTY="$1"
	local IP=$(echo $DIRTY | awk -F. '$1 <=255 && $2 <= 255 && $3 <= 255 && $4 <= 255 ')

	if [ -z "$IP" ]; then
		return 1
	else
		echo true
		return 0
	fi
}

##
# Get IP
# Returns the first IP match to the hostname provided
#
# param HOSTNAME Host for which to retrieve an IP
#
# return IP|false
##
ch_get_ip()
{
	local HOST="$1"
	#So, if there's multiple IP addresses, just grab the first
	# for now.
	local CHECK_IP=$(host -t A $HOST | awk 'NR==1{ print $4 }')

	if [ ! `ch_is_ip "$CHECK_IP"` ]; then
		# Try a dig, why not?
		CHECK_IP=$(dig +short $HOST | tac | awk 'NR==1{ print $1 }')

		if [ ! `ch_is_ip "$CHECK_IP"` ]; then
			return 1
		fi
	fi

	echo $CHECK_IP
	return 0
}
