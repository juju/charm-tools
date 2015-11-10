#!/bin/sh
#
# Run this with 'expected' as the argument to update the
# expected dir which should be stored in version control.
#
# test.sh will run it with 'results' and diff the two when
# running tests.
#
home=`dirname $0`
test_charms=$home/../charms
# ensure output dir exists and is empty
rm -f $home/$1; mkdir -p $home/$1
for i in $test_charms/* ; do
    $home/../../.tox/py27/bin/python $home/../../charmtools/proof.py $i > $home/$1/`basename $i`
done
