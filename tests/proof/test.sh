#!/bin/sh
home=`dirname $0`
sh $home/record.sh results
if ! diff -ur $home/expected $home/results ; then
    echo "Differences detected (see above). Abort!"
    exit 1
fi
