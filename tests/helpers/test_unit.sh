#!/bin/sh

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

JUJU_UNIT_NAME="test/9001"

. $HELPERS_HOME/unit.sh

start_test ch_unit_name...
[ "`ch_unit_name $JUJU_UNIT_NAME`" = "test" ]
[ "`ch_service_name $JUJU_UNIT_NAME`" = "test" ]
echo PASS

start_test ch_unit_id...
[ "`ch_unit_id $JUJU_UNIT_NAME`" = "9001" ]
echo PASS

start_test ch_my_unit_id...
[ "`ch_my_unit_id`" = "9001" ]
echo PASS
