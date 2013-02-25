#!/bin/sh
set -e
repository=$1
if [ -z "$repository" ] ; then
    echo "usage: $0 path/to/repository | teardown"
    exit 1
fi

JUJU=`which juju`

if [ "$repository" = "teardown" ] ; then
    $JUJU destroy-service master
    $JUJU destroy-service slave
    $JUJU destroy-service demowiki
    exit 0
fi

$JUJU deploy --repository=$repository local:mysql master
$JUJU deploy --repository=$repository local:mysql slave
$JUJU add-relation master:master slave:slave
$JUJU deploy --repository=$repository local:mediawiki demowiki
$JUJU add-relation master:db demowiki:db
$JUJU add-relation slave:db demowiki:slave
