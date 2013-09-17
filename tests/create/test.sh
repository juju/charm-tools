#!/bin/sh

TESTDIR=`dirname $0`
CREATE=$TESTDIR/../../charmtools/create.py

cleanup() {
    if [ -n "$workdir" ] && [ -d "$workdir" ] ; then
        rm -rf $workdir
    fi
}
trap cleanup EXIT

workdir=`mktemp -d /tmp/tests.XXXXXX`

# These will influence create's maintainer generation and should also
# be set when updating the test charms
export UBUMAIL=test@testhost
export EMAIL=$UBUMAIL
export DEBFULLNAME=tester
export NAME=$DEBFULLNAME

echo ===== Creating no-package-exists test charm =====
$CREATE no-package-exists $workdir
set -e

compare_charms() {
    local newcharm=$1
    local newname=`basename $newcharm`
    echo `date`: comparing newly generated $newcharm to test generated charm.
    [ -d $newcharm ]
    [ -f $newcharm/metadata.yaml ]
    diff -ur $TESTDIR/$newname $newcharm
}

compare_charms $workdir/no-package-exists

echo ===== Expected failure when trying to create again =====
if $CREATE no-package-exists $workdir ; then
    echo FAIL - should see that the charm was there already.
    exit 1
fi

echo ===== Now try with apt package information populated. =====
if python -c 'import apt' ; then
    $CREATE python-apt $workdir
    compare_charms $workdir/python-apt
else
    echo SKIP python apt module not present, skipping apt tests
fi

echo ===== All tests passed! =====
echo PASS
set +e
trap - EXIT
cleanup
exit 0
