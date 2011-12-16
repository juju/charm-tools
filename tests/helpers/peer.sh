#!/bin/sh
set -ue

test_home=`dirname $0`
test_home=`readlink -f $test_home`

# Should set 60 second timeout
if [ -z ${1:-""} ] ; then
    exec $test_home/run_with_timeout.py $0 timeout
fi

PEER_SOURCE=${PEER_SOURCE:-"$test_home/../../helpers/sh/peer.sh"}

#mock relation-list
HELPERS_TEST=1
alias relation-list=relation_list
relation_list()
{
    echo "TEST/2
TEST/3
TEST/4"
}

output () {
    echo `date`: $*
}

start_output () {
    echo -n `date`: $*
}

start_test () {
    echo -n `date`: Testing $*
}


# Uncomment this to get more info on why wget failed
#CH_WGET_ARGS="--verbose"

. $PEER_SOURCE

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
