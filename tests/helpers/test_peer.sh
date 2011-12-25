#!/bin/sh
debug=1

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

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

#Save juju-log for debugging
CH_TEMPLOG="/tmp/tmp-juju-log"
echo "" > $CH_TEMPLOG
output "creating test-log in $CH_TEMPLOG"
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

CH_TEMPDIR=""

created_ssh_home=0

cleanup_peer()
{
    [ $debug = 1 ] && output "sshd server log" ; cat /tmp/juju-sshd-log
    output "Cleaning up..."
    unalias juju-log
    unalias relation-set
    unalias relation-get
    unalias unit-get
    unalias relation-list
    [ -n "$CH_TEMPDIR" ] || return 0
    [ ! -f $CH_TEMPDIR/sshd.pid ] || kill -9 `cat $CH_TEMPDIR/sshd.pid`
    rm -rf $CH_TEMPDIR
    if [ $created_ssh_home = 1 ] ; then
        backup_dir=`mktemp -d /tmp/backup-charm-helper.ssh.XXXXXXXX`
        output "Backing up created $HOME/.ssh to $backup_dir/dot-ssh"
        mv $HOME/.ssh $backup_dir/dot-ssh
    fi
}
trap cleanup_peer EXIT
if [ ! -d $HOME ] ; then
    mkdir -p $HOME
    chown $USER:$USER $HOME
    chmod 700 $HOME
fi
if [ ! -d $HOME/.ssh ] ; then
    mkdir -p $HOME/.ssh
    chmod 700 $HOME/.ssh
    created_ssh_home=1
else
    output "ch_peer_scp can be destructive to \$HOME/.ssh, move it out of the way or"
    output "run these tests in a clean chroot or with a test user. Skipping."
    exit 0
fi
touch $HOME/.ssh/authorized_keys
touch $HOME/.ssh/known_hosts
chmod 600 $HOME/.ssh/authorized_keys
chmod 644 $HOME/.ssh/known_hosts

# mock sshd server
CH_TEMPDIR=`mktemp -d "/tmp/juju-helpers-tmp.XXXXXXX"`
mkdir -p $CH_TEMPDIR/sourcedir/
mkdir -p $CH_TEMPDIR/destdir/
mkdir -p $CH_TEMPDIR/$HOME/
if ! mkdir -p /var/run/sshd ; then
    mkdir -p $HOME/var/run/sshd/
fi
# Protect user's normal home dir
head -c 16384 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile0
head -c 32385 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile1
head -c 19998 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile
CH_portnum=28822
ssh-keygen -t rsa -b 1024 -N "" -h -f $CH_TEMPDIR/my_host_key > /dev/null 2>&1 
if [ $debug = 1 ] ; then
    /usr/sbin/sshd -e -o PidFile=$CH_TEMPDIR/sshd.pid -o UsePrivilegeSeparation=no -o StrictModes=no -d -h $CH_TEMPDIR/my_host_key -p $CH_portnum 2> /tmp/juju-sshd-log &
    listening=1
else
    # wait for server
    output "waiting for sshd to be available"
    listening=0
    for i in 1 2 3 4 5 ; do
      sleep 1
      ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no -p $CH_portnum bozo@localhost 2> /tmp/result ||
      if grep -q -F "Permission denied" /tmp/result ; then
        output Attempt $i succeeded.
        listening=1
        break
      fi
      output Attempt $i failed..
    done
    if [ $listening = 0 ] ; then
        exit 1
    fi
fi

. $HELPERS_HOME/peer.sh

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
CH_MASTER=1
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
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2"  
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    if ch_peer_scp -r -p $CH_portnum -o "-v" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    if [ $debug = 1 ] ; then
        if ch_peer_scp -r -p $CH_portnum -o "-v" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
    else
        if ch_peer_scp -r -p $CH_portnum -o "-q" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
    fi
done
[ ! -e $CH_TEMPDIR/destdir/ ] && output "dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && output "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && output "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
echo PASS

start_test "ch_peer_rsync..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2"  
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    if ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    if ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
done
[ ! -e $CH_TEMPDIR/destdir/ ] && output"dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && output "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && output "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
echo PASS

start_test "ch_peer_scp..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2" 
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    if ch_peer_scp -p $CH_portnum -o "-q" $CH_TEMPDIR/sourcedir/testfile $CH_TEMPDIR/destdir/ ; then break ; fi
    #master relation joined
    JUJU_UNIT_NAME="TEST/1" 
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    if ch_peer_scp -p $CH_portnum -o "-q" $CH_TEMPDIR/sourcedir/testfile $CH_TEMPDIR/destdir/ ; then break ; fi
done
[ ! -e $CH_TEMPDIR/destdir/testfile ] && output"file not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
echo PASS

trap - EXIT
cleanup_peer
