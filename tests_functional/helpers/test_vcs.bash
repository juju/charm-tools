#!/bin/bash

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

MOCK_NET=${MOCK_NET:-"true"}
MOCK_VCS=${MOCK_VCS:-"true"}

mock_host()
{
    if echo $* | grep -q "[_#]" ; then return 1 ; fi
    echo nothost.local has address 127.0.0.1
    echo nothost.local has address 127.0.1.1
}

mock_dig()
{
    if echo $* | grep -q "[_#]" ; then return 1 ; fi
    echo 127.0.0.1
    echo 127.0.1.1
}

mock_git()
{
	if [ "$1" = "clone" ] && [ $# -eq 3 ]; then
		return 0
	fi

	if [ "$1" = "pull" ] && [ $# -eq 1 ]; then
		return 0
	fi

	return 1
}

mock_bzr()
{
	if [ "$1" = "branch" ] && [ $# -eq 3 ]; then
		return 0
	fi

	if [ "$1" = "pull" ] && [ $# -eq 1 ]; then
		return 0
	fi

	return 1
}

mock_svn()
{
	if [ "$1" = "co" ] && [ $# -eq 4 ]; then
		return 0
	fi

	if [ "$1" = "up" ] && [ $# -eq 1 ]; then
		return 0
	fi

	return 1
}

mock_apt()
{
	return 0
}

if [ "$MOCK_NET" = "true" ]; then
    alias host=mock_host
    alias dig=mock_dig
fi

## At this time, this doesn't work, but one day it will - or at least should
## Assuming that ch_detect_vcs works, ch_fetch_repo and ch_update_repo
## should run without issue.
if [ "$MOCK_VCS" = "true" ]; then
	alias git=mock_git
	alias bzr=mock_bzr
	alias svn=mock_svn
	alias hg=mock_git
	alias apt-get=mock_apt
fi

CH_VCS_INSTALL_DEPS="false"

. $HELPERS_HOME/vcs.bash

cleanup_repos()
{
	output Cleaning up fake repos...
	rm -rf /tmp/charm-helper-vcs-*
}

trap cleanup_repos EXIT

output Creating fake local repos...
temp_no_vcs=`mktemp -d /tmp/charm-helper-vcs-lol.XXXXXX`
temp_git_dir=`mktemp -d /tmp/charm-helper-vcs-git.XXXXXX`
temp_bzr_dir=`mktemp -d /tmp/charm-helper-vcs-bzr.XXXXXX`
temp_svn_dir=`mktemp -d /tmp/charm-helper-vcs-svn.XXXXXX`
temp_hg_dir=`mktemp -d /tmp/charm-helper-vcs-hg.XXXXXX`

mkdir -p $temp_git_dir/.git
mkdir -p $temp_bzr_dir/.bzr
mkdir -p $temp_svn_dir/.svn
mkdir -p $temp_hg_dir/.hg

start_test ch_detect_vcs...
ch_detect_vcs "notvalid" && return 1 || :
[ "`ch_detect_vcs 'lp:charm-tools'`" = "bzr" ]
[ "`ch_detect_vcs 'lp:~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_detect_vcs 'bzr+ssh://example.com/~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_detect_vcs 'bzr+ssh://example.com/~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_detect_vcs $temp_bzr_dir`" = "bzr" ]
[ "`ch_detect_vcs 'https://example.com/charm-tools.git'`" = "git" ]
[ "`ch_detect_vcs 'http://example.com/charm-tools.git'`" = "git" ]
[ "`ch_detect_vcs 'git://example.com/charm-tools.git'`" = "git" ]
[ "`ch_detect_vcs 'git@example.com/charm-tools.git'`" = "git" ]
[ "`ch_detect_vcs $temp_git_dir`" = "git" ]
[ "`ch_detect_vcs 'svn+ssh://example.com/charm-tools/trunk'`" = "svn" ]
[ "`ch_detect_vcs 'svn://example.com/charm-tools/trunk'`" = "svn" ]
[ "`ch_detect_vcs $temp_svn_dir`" = "svn" ]
[ "`ch_detect_vcs $temp_hg_dir`" = "hg" ]
echo PASS

# TODO
#start_test ch_fetch_repo...
#echo DEFERRED

# TODO
#start_test ch_update_repo...
#echo DEFERRED

trap - EXIT
cleanup_repos
