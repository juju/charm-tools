#!/bin/sh

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
	
	if [ "$1" == "up" ] && [ $# -eq 1 ]; then
		return 0
	fi

	return 1
}

if [ "$MOCK_NET" = "true" ]; then
    alias host=mock_host
    alias dig=mock_dig    
fi

if [ "$MOCK_VCS" = "true" ]; then
	alias git=mock_git
	alias bzr=mock_bzr
	alias svn=mock_svn
	alias hg=mock_git
fi

. $HELPERS_HOME/vcs.sh

start_test ch_detect_vcs...
ch_detect_vcs "not even a URL" && return 1 || :
[ "`ch_detect_vcs 'lp:charm-tools'`" = "bzr" ]
[ "`ch_detect_vcs 'lp:~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_detect_vcs 'bzr+ssh://bazaar.launchpad.net/~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_detect_vcs 'bzr+ssh://bazaar.launchpad.net/~charmers/charm-tools/trunk'`" = "bzr" ]
[ "`ch_is_url 'https://launchpad.net'`" = "true" ]
echo PASS

trap - EXIT
cleanup_temp
