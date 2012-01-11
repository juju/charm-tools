#!/bin/sh

# debug=1 full
# debug=2 client only
debug=0

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

JUJU_UNIT_NAME="EMPTY"

#mock relation-list
alias relation-list=mock_relation_list
mock_relation_list()
{
    [ -z $CH_MASTER ] && let CH_MASTER=1
    
    case $CH_MASTER in
    4)
        echo "TEST/3
TEST/2
TEST/4"
        ;;
    3)
        echo "TEST/4
TEST/3
TEST/1"
        ;;
    2)
        echo "TEST/3
TEST/4"
        ;;
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
    -1)
        echo ""
        ;;
    esac 

}

#Save juju-log for debugging
CH_TEMPLOG="/tmp/$USER-tmp-juju-log"
echo "" > $CH_TEMPLOG
output "creating test-log in $CH_TEMPLOG"
alias juju-log=mock_juju_log
mock_juju_log()
{
    echo "$*" >> $CH_TEMPLOG
}

#mock unit-get
alias unit-get=mock_unit_get
mock_unit_get()
{
   case $1 in
   "private-address")
       echo "localhost"
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
    [ $debug = 1 ] && output "====== sshd server log ======" && cat /tmp/juju-sshd-log ; rm -f /tmp/juju-sshd-log
    [ $debug -gt 1 ] && output "===== juju debug log ======" && cat $CH_TEMPLOG
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
    if [ -e $HOME/ch_test ] ; then
        rm -rf $HOME/ch_test
    fi
}
trap cleanup_peer EXIT
if [ $debug -gt 0 ] ; then echo "user: $USER, home: $HOME"; fi
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
if [ x"$USER" = x"root" ] ; then
    if ! touch /root/.ssh/known_hosts ; then
        USER=`basename $HOME`
        echo "forcing user to: $USER"
    fi
fi
touch $HOME/.ssh/authorized_keys
touch $HOME/.ssh/known_hosts
chmod 600 $HOME/.ssh/authorized_keys

# mock sshd server
CH_TEMPDIR=`mktemp -d "/tmp/juju-helpers-tmp.XXXXXXX"`
mkdir -p $CH_TEMPDIR/sourcedir/
mkdir -p $CH_TEMPDIR/destdir/
mkdir -p $CH_TEMPDIR/$HOME/
if ! [ -d /var/run/sshd ] ; then
    if ! mkdir -p /var/run/sshd ; then
        mkdir -p $HOME/var/run/sshd/
    fi
fi
# Protect user's normal home dir
head -c 16384 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile0
head -c 32385 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile1
head -c 19998 /dev/urandom > $CH_TEMPDIR/sourcedir/testfile
CH_portnum=28822
# lucid's ssh-keygen does not accept -h, so we check for maverick or
# later to add -h
ssh_version=`dpkg -l 'openssh-client'|awk '/^ii/ { print $3 }'`
if dpkg --compare-versions $ssh_version lt 1:5.5p1-4ubuntu4 ; then
  opts=""
else
  opts="-h"
fi
ssh-keygen -t rsa -b 1024 -N "" $opts -f $CH_TEMPDIR/my_host_key > /dev/null 2>&1 
if [ $debug = 1 ] ; then
    /usr/sbin/sshd -e -o PidFile=$CH_TEMPDIR/sshd.pid -o UsePrivilegeSeparation=no -o StrictModes=no -d -h $CH_TEMPDIR/my_host_key -p $CH_portnum 2> /tmp/juju-sshd-log &
    CH_scpopt="-v"
    listening=1
else
    /usr/sbin/sshd -e -o PidFile=$CH_TEMPDIR/sshd.pid -o UsePrivilegeSeparation=no -o StrictModes=no -h $CH_TEMPDIR/my_host_key -p $CH_portnum
    # wait for server
    output "waiting for sshd to be available"
    listening=0
    ch_tmp_result=`mktemp`
    for i in 1 2 3 4 5 ; do
      sleep 1

      ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=no -p $CH_portnum bozo@localhost 2> $ch_tmp_result ||
      if grep -q -F "Permission denied" $ch_tmp_result ; then
        output Attempt $i succeeded.
        listening=1
        break
      fi
      output Attempt $i failed..
    done
    rm -f $ch_tmp_result
    if [ $listening = 0 ] ; then
        exit 1
    fi
    if [ $debug -gt 0 ]; then CH_scpopt="-v" ; else CH_scpopt="-q"; fi;
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

start_test "ch_peer_i_am_leader (unordered list 1)..."
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/2"
CH_MASTER=3
ch_peer_i_am_leader && return 1 || :
echo PASS

start_test "ch_peer_i_am_leader (unordered list 2)..."
JUJU_UNIT_NAME="TEST/1"
CH_MASTER=4
ch_peer_i_am_leader || return 1 && :
echo PASS

start_test "ch_peer_i_am_leader (unordered list 3)..."
JUJU_UNIT_NAME="TEST/2"
CH_MASTER=3
ch_peer_i_am_leader && return 1 || :
echo PASS

start_test "ch_peer_i_am_leader (unordered list 4)..."
JUJU_UNIT_NAME="TEST/3"
ch_peer_i_am_leader && return 1 && :
echo PASS

start_test "ch_peer_i_am_leader (empty list)..."
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/1"
CH_MASTER=-1
ch_peer_i_am_leader || return 1 && :
echo PASS

start_test "ch_peer_i_am_leader (departed leader)..."
JUJU_REMOTE_UNIT="TEST/1"
JUJU_UNIT_NAME="TEST/4"
CH_MASTER=2
ch_peer_i_am_leader && return 1 || :
JUJU_UNIT_NAME="TEST/2"
ch_peer_i_am_leader || return 1 && :
echo PASS

start_test ch_peer_leader...
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/1"
CH_MASTER=1
[ "`ch_peer_leader`" = "TEST/1" ] ||  return 1
[ `ch_peer_leader --id` -eq 1 ] || return 1
JUJU_UNIT_NAME="TEST/2"
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
    if ch_peer_scp -r -p $CH_portnum -o "$CH_scpopt" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    if ch_peer_scp -r -p $CH_portnum -o "$CH_scpopt" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" ; then break ; fi
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
    if ch_peer_scp -p $CH_portnum -o "-q" "$CH_TEMPDIR/sourcedir/testfile" "$CH_TEMPDIR/destdir/" "$CH_TEMPDIR/sourcedir/testfile1" "$CH_TEMPDIR/destdir/" ; then break ; fi
    #master relation joined
    JUJU_UNIT_NAME="TEST/1" 
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    if ch_peer_scp -p $CH_portnum -o "-q" "$CH_TEMPDIR/sourcedir/testfile" "$CH_TEMPDIR/destdir/" "$CH_TEMPDIR/sourcedir/testfile1" "$CH_TEMPDIR/destdir/" ; then break ; fi
done
[ ! -e $CH_TEMPDIR/destdir/testfile ] && output "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && output "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
echo PASS

start_test "ch_peer_copy_replay..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
#We are not in a relation, we are on master
JUJU_UNIT_NAME="TEST/1" 
JUJU_REMOTE_UNIT=""
CH_MASTER=-1
if ! ch_peer_copy_replay ; then
    output "should not have returned not copied (1)"
    exit 1
fi
#We are not in a relation, we are on slave
JUJU_UNIT_NAME="TEST/2" 
JUJU_REMOTE_UNIT=""
CH_MASTER=-1
if ch_peer_copy_replay ; then
    output "should not have returned copied (0)"
    exit 1
fi
[ ! -e $CH_TEMPDIR/destdir/testfile ] && output "file not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
[ ! -e $CH_TEMPDIR/destdir/ ] && output "dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && output "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && output "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
echo PASS

start_test "ch_peer_rsync (out of relation)..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
#We are not in a relation, we are on master
JUJU_UNIT_NAME="TEST/1" 
JUJU_REMOTE_UNIT=""
CH_MASTER=-1
ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" && chres=0 || chres=$?
if [ $chres -ne 101 ] ; then
    output "should not have returned not copied (received $chres, 101 expected)"
    exit 1
fi
#We are not in a relation, we are on slave
JUJU_UNIT_NAME="TEST/2" 
JUJU_REMOTE_UNIT=""
CH_MASTER=-1
ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" && chres=0 || chres=$?
if [ $chres -ne 100 ] ; then
    output "should not have returned copied (received $chres, 100 expected)"
    exit 1
fi
[ ! -e $CH_TEMPDIR/destdir/ ] && output "dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && output "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && output "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && output "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
#restore authorized_keys & known_hosts
echo PASS

start_test "ch_peer_copy_cleanup..."
# as a leader
JUJU_UNIT_NAME="TEST/1" 
JUJU_REMOTE_UNIT="TEST/2"
CH_MASTER=-1
ch_peer_copy_cleanup "$JUJU_REMOTE_UNIT"
unitname=`echo $JUJU_UNIT_NAME | sed 's/\//-/g'`
[ `grep -F "$JUJU_REMOTE_UNIT" $HOME/ch_test/$unitname` ] && output "not cleaned up" && exit 1
# as a slave
JUJU_UNIT_NAME="TEST/2" 
JUJU_REMOTE_UNIT="TEST/1"
CH_MASTER=-1
ch_peer_copy_cleanup "$JUJU_REMOTE_UNIT"
#nothing to check here other than if we did not choke on cleaning up something that does not exist
echo PASS

trap - EXIT
cleanup_peer
