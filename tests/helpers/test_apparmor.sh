#!/bin/sh

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

mock_service() {
    echo $* >> $SERVICE_LOG
}
alias service=mock_service

. $HELPERS_HOME/apparmor.sh

CHARM_DIR=""
SERVICE_LOG=""
CH_APPARMOR_DESTDIR=""

cleanup_apparmor() {
    if [ -n "$CHARM_DIR" ] && [ -d "$CHARM_DIR" ] ; then
        rm -rf $CHARM_DIR
    fi
    if [ -n "$CH_APPARMOR_DESTDIR" ] && [ -d "$CH_APPARMOR_DESTDIR" ] ; then
        rm -rf $CH_APPARMOR_DESTDIR
    fi
    if [ -n "$SERVICE_LOG" ] && [ -f "$SERVICE_LOG" ] ; then
        rm -rf $SERVICE_LOG
    fi
}

trap cleanup_apparmor EXIT

CHARM_DIR=`mktemp -d /tmp/ch_charm_dir.XXXXXX`
CH_APPARMOR_DESTDIR=`mktemp -d /tmp/ch_apparmor_root.XXXXXX`
SERVICE_LOG=`mktemp /tmp/service_log.XXXXXX`

mkdir -p $CHARM_DIR/apparmor/profiles.d
mkdir -p $CH_APPARMOR_DESTDIR/etc/apparmor.d
cat > $CHARM_DIR/apparmor/profiles.d/usr.bin.foo <<EOF
/usr/lib/telepathy/telepathy-* {
    #include <abstractions/base>
}
EOF

start_test ch_apparmor_load...
ch_apparmor_load
[ -f $CH_APPARMOR_DESTDIR/etc/apparmor.d/usr.bin.foo ]
cmp $CH_APPARMOR_DESTDIR/etc/apparmor.d/usr.bin.foo $CHARM_DIR/apparmor/profiles.d/usr.bin.foo
grep -q "apparmor reload" $SERVICE_LOG
cp /dev/null $SERVICE_LOG
echo PASS

trap - EXIT
cleanup_apparmor
