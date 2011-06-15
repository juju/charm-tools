#!/bin/sh
set -e
repository=$1
if [ -z "$repository" ] ; then
  echo "usage: $0 path/to/repository|teardown"
  exit 1
fi

ENSEMBLE=`which ensemble`

if [ "$repository" = "teardown" ] ; then
  $ENSEMBLE destroy-service wiki-db || echo could not teardown wiki-db
  $ENSEMBLE destroy-service demo-wiki || echo could not teardown demo-wiki
  $ENSEMBLE destroy-service wiki-cache || echo could not teardown wiki-cache
  $ENSEMBLE destroy-service wiki-balancer || echo could not teardown wiki-balancer
  exit 0
fi

$ENSEMBLE deploy --repository=$repository mysql wiki-db
$ENSEMBLE deploy --repository=$repository mediawiki demo-wiki
$ENSEMBLE deploy --repository=$repository memcached wiki-cache
$ENSEMBLE deploy --repository=$repository haproxy wiki-balancer
$ENSEMBLE add-unit wiki-cache
$ENSEMBLE add-unit demo-wiki
$ENSEMBLE add-relation wiki-db:db demo-wiki:db
$ENSEMBLE add-relation wiki-cache demo-wiki
$ENSEMBLE add-relation wiki-balancer:reverseproxy demo-wiki:website
$ENSEMBLE status
