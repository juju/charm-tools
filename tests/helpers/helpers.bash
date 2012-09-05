#!/bin/bash

set -ue

test_home=`dirname $0`
test_home=`readlink -f $test_home`

# Should set 60 second timeout
if [ -z ${1:-""} ] ; then
    exec $test_home/run_with_timeout.py $0 timeout
fi

[ "${LIB_SOURCED:-''}" = "1" ] || . $test_home/lib.sh

for i in $test_home/test_*.bash ; do
  . $i
done

