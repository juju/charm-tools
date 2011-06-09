#!/bin/sh
set -e
repository=$1
if [ -z "$repository" ] ; then
  echo "usage: $0 path/to/repository | teardown"
  exit 1
fi

ENSEMBLE=`which ensemble`

if [ "$repository" = "teardown" ] ; then
  $ENSEMBLE destroy-service master
  $ENSEMBLE destroy-service slave
  $ENSEMBLE destroy-service demowiki
  exit 0
fi

$ENSEMBLE deploy --repository=$repository mysql master
$ENSEMBLE deploy --repository=$repository mysql slave
$ENSEMBLE add-relation master:master slave:slave
$ENSEMBLE deploy --repository=$repository mediawiki demowiki
$ENSEMBLE add-relation master:db demowiki:db
$ENSEMBLE add-relation slave:db demowiki:slave
