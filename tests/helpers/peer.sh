#!/bin/sh
set -ue

test_home=`dirname $0`
test_home=`readlink -f $test_home`

# Should set 60 second timeout
if [ -z ${1:-""} ] ; then
    exec $test_home/run_with_timeout.py $0 timeout
fi

PEER_SOURCE=${PEER_SOURCE:-"$test_home/../../helpers/sh/peer.sh"}

#mock relation-list
alias relation-list=mock_relation_list
mock_relation_list()
{
    [ -z $CH_MASTER ] && let CH_MASTER=1
    
    case $CH_MASTER in
    1)
        echo "TEST/2
TEST/3
TEST/4"
        ;;
    0)
        echo "TEST/1
TEST/3
TEST/4"
        ;;
    esac
        
}

CH_TEMPLOG="/tmp/tmp-juju-log"
alias juju-log=mock_juju_log
mock_juju_log()
{
    echo "$1" >> $CH_TEMPLOG
}

#mock unit-get
alias unit-get=mock_unit_get
mock_unit_get()
{
   case $1 in
   "private-address")
       echo "127.0.0.1"
       ;;
   *)
       echo "UNDEFINED"
       ;;
   esac
}

#mock relation-set/get
alias relation-set=mock_relation_set
alias relation-get=mock_relation_get
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
mock_relation_set()
{
    juju-log "mock_relation_set: $1"
    CH_varname=`echo $1 | cut -d= -f1`
    CH_value=`echo $1 | sed 's/^[^=]*=//'`
    case $CH_varname in
    "scp-hostname")
        CH_scp_hostname=$CH_value
        ;;
    "scp-ssh-key-saved")
        CH_scp_ssh_key_saved=$CH_value
        ;;
    "scp-ssh-key")
        CH_scp_ssh_key="$CH_value"
        ;;
    "scp-copy-done")
        CH_scp_copy_done=$CH_value
        ;;
    *)
        juju-log "mock_relation_set: unknow var $CH_varname"
        ;;
    esac
}
mock_relation_get()
{
    case $1 in
    "scp-hostname")
        echo $CH_scp_hostname
        juju-log "mock_relation_get: $1 = $CH_scp_hostname"
        ;;
    "scp-ssh-key-saved")
        echo $CH_scp_ssh_key_saved
        juju-log "mock_relation_get: $1 = $CH_scp_ssh_key_saved"
        ;;
    "scp-ssh-key")
        echo "$CH_scp_ssh_key"
        juju-log "mock_relation_get: $1 = $CH_scp_ssh_key"
        ;;
    "scp-copy-done")
        echo $CH_scp_copy_done
        juju-log "mock_relation_get: $1 = $CH_scp_copy_done"
        ;;
    *)
        juju-log "mock_relation_get: unknow var $1"
        ;;
    esac
}


# mock sshd server
CH_TEMPDIR=`mktemp -d`
CH_CHROOT="$CH_TEMPDIR/chroot"
mkdir -p $CH_CHROOT/$HOME/.ssh
touch  $CH_CHROOT/$HOME/.ssh/authorized_keys
mkdir -p $CH_CHROOT/$CH_TEMPDIR
mkdir -p $CH_CHROOT/var/run
mkdir -p $CH_CHROOT/var/log
mkdir -p $CH_CHROOT/usr/bin
cp -R /usr/bin $CH_CHROOT/usr/bin
mkdir -p $CH_CHROOT/etc/ssh
cp -R /etc/ssh $CH_CHROOT/etc/ssh > /dev/null ||
mkdir -p $CH_TEMPDIR/testdir
pwgen > $CH_TEMPDIR/testdir/testfile0
pwgen > $CH_TEMPDIR/testdir/testfile1
pwgen > $CH_TEMPDIR/testfile
CH_portnum=8822
/usr/sbin/sshd -o ChrootDirectory=$CH_CHROOT -o PidFile=$CH_CHROOT/var/run/sshd.pid -p $CH_portnum
CH_cleanup_sshd()
{
    kill -9 `cat $CH_CHROOT/var/run/sshd.pid`
    rm -rf $CH_TEMPDIR
    unalias juju-log
    unalias relation-set
    unalias relation-get
    unalias unit-get
    unalias relation-list
}

output () {
    echo `date`: $*
}

start_output () {
    echo -n `date`: $*
}

start_test () {
    echo -n `date`: Testing $*
}


# Uncomment this to get more info on why wget failed
#CH_WGET_ARGS="--verbose"

. $PEER_SOURCE

start_test ch_unit_id...
JUJU_UNIT_NAME="TEST/1"
[ ! `ch_unit_id $JUJU_UNIT_NAME` -eq 1 ] && return 1
CH_bad="badarg"
ch_unit_id $CH_bad > /dev/null || return 1
echo PASS

start_test ch_my_unit_id...
[ ! `ch_my_unit_id` -eq  1 ] && return 1
echo PASS

start_test ch_peer_i_am_leader...
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/2"
ch_peer_i_am_leader && return 1 || :
JUJU_UNIT_NAME="TEST/1"
ch_peer_i_am_leader || return 1 && :
echo PASS

start_test ch_peer_leader...
[ "`ch_peer_leader`" = "TEST/1" ] ||  return 1
[ `ch_peer_leader --id` -eq 1 ] || return 1
JUJU_UNIT_NAME="TEST/3"
[ "`ch_peer_leader`" = "TEST/2" ] || return 1
[ `ch_peer_leader --id` -eq 2 ] || return 1
echo PASS

start_test "ch_peer_scp -r..."
for i in 1 2 3 4
do
    echo "Begin $i"
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2"  
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    ch_peer_scp -r -p $CH_portnum $CH_TEMPDIR/testdir
    echo "middle $i"
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    ch_peer_scp -r -p $CH_portnum $CH_TEMPDIR/testdir
    echo "End $i"
done
[ ! -e $CH_CHROOT/$CH_TEMPDIR/testdir ] && echo "dir not copied" && exit 1
[ ! -e $CH_CHROOT/$CH_TEMPDIR/testdir/testfile0 ] && echo "file1 not copied" && exit 1
[ ! -e $CH_CHROOT/$CH_TEMPDIR/testdir/testfile0 ] && echo "file2 not copied" && exit 1
CH_t1=`md5sum $CH_CHROOT/$CH_TEMPDIR/testdir/testfile0`
CH_t2=`md5sum $CH_TEMPDIR/testdir/testfile0`
[ ! "$CH_t1" = "$CH_t2" ] && echo "md5sum differ" && exit 1
rm -rf $CH_CHROOT/$CH_TEMPDIR/testdir
echo PASS


start_test "ch_peer_scp..."
for i in 1 2 3 4
do
    mock_juju_log "Begin $i"
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2" 
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    ch_peer_scp -p $CH_portnum $CH_TEMPDIR/testfile
    #master relation joined
    JUJU_UNIT_NAME="TEST/1" 
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    ch_peer_scp -p $CH_portnum $CH_TEMPDIR/testfile
    mock_juju_log "End $i"
done
[ ! -e $CH_CHROOT/$CH_TEMPDIR/testfile ] && echo "file not copied" && exit 1
CH_t1=`md5sum $CH_CHROOT/$CH_TEMPDIR/testfile`
CH_t2=`md5sum /$CH_TEMPDIR/testfile`
[ ! "$CH_t1" = "$CH_t2" ] && echo "md5sum differ" && exit 1
rm -rf $CH_CHROOT/$CH_TEMPDIR/testfile
echo PASS
