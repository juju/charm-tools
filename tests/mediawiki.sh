#!/bin/sh
set -e
repository=$1
if [ -z "$repository" ] ; then
    echo "usage: $0 path/to/repository|teardown"
    exit 1
fi

JUJU=`which juju`

if [ "$repository" = "teardown" ] ; then
    $JUJU destroy-service wiki-db || echo could not teardown wiki-db
    $JUJU destroy-service demo-wiki || echo could not teardown demo-wiki
    $JUJU destroy-service wiki-cache || echo could not teardown wiki-cache
    $JUJU destroy-service wiki-balancer || echo could not teardown wiki-balancer
    exit 0
fi

$JUJU deploy --repository=$repository local:mysql wiki-db
$JUJU deploy --repository=$repository local:mediawiki demo-wiki
$JUJU deploy --repository=$repository local:memcached wiki-cache
$JUJU deploy --repository=$repository local:haproxy wiki-balancer
$JUJU add-unit wiki-cache
$JUJU add-unit demo-wiki
$JUJU add-relation wiki-db:db demo-wiki:db
$JUJU add-relation wiki-cache demo-wiki
$JUJU add-relation wiki-balancer:reverseproxy demo-wiki:website
$JUJU status
