#!/bin/bash

TESTDIR=`dirname $0`

# activate virtualenv
source $TESTDIR/../../.tox/py27/bin/activate

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

echo ===== Creating test charm for 'charm add' tests =====
charm create -t bash testcharm $workdir
set -e

cd $workdir/testcharm
rm -rf icon.svg README.ex

echo ===== Testing 'charm add tests' =====
charm add tests
if [ ! -d tests ] ; then
  echo FAIL - tests directory not created
  exit 1
fi

echo ===== Testing 'charm add readme' =====
charm add readme
if [ ! -f README.ex ] ; then
  echo FAIL - README.ex file not created
  exit 1
fi

echo ===== Testing 'charm add icon' =====
charm add icon
if [ ! -f icon.svg ] ; then
  echo FAIL - icon.svg file not created
  exit 1
fi

echo ===== All tests passed! =====
echo PASS
set +e
trap - EXIT
cleanup
exit 0
