#!/bin/sh
if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

#mock relation-list
alias relation-list=relation_list
relation_list()
{
    echo "TEST/2
TEST/3
TEST/4"
}

. $HELPERS_HOME/peer.sh

start_test ch_unit_id...
JUJU_UNIT_NAME="TEST/1"
[ ! `ch_unit_id $JUJU_UNIT_NAME` -eq 1 ] && return 1
CH_bad="badarg"
ch_unit_id $CH_bad > /dev/null || return 1
echo PASS

start_test ch_my_unit_id...
[ ! `ch_my_unit_id` -eq  1 ] && return 1
echo PASS

start_test ch_peer_i_am_leader...
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/2"
ch_peer_i_am_leader && return 1 || :
JUJU_UNIT_NAME="TEST/1"
ch_peer_i_am_leader || return 1 && :
echo PASS

start_test ch_peer_leader...
[ "`ch_peer_leader`" = "TEST/1" ] ||  return 1
[ `ch_peer_leader --id` -eq 1 ] || return 1
JUJU_UNIT_NAME="TEST/3"
[ "`ch_peer_leader`" = "TEST/2" ] || return 1
[ `ch_peer_leader --id` -eq 2 ] || return 1
echo PASS
