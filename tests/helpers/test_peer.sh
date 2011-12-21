#!/bin/sh
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
echo "creating test-log in $CH_TEMPLOG"
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
CH_TEMPDIR="/tmp/`mktemp -d "/tmp/juju-helpers-tmp.XXXXXXX"`"
mkdir -p $CH_TEMPDIR/sourcedir/
mkdir -p $CH_TEMPDIR/destdir/
mkdir -p $CH_TEMPDIR/$HOME/
[ ! `which pwgen` ] && apt-get -y install pwgen
pwgen > $CH_TEMPDIR/sourcedir/testfile0
pwgen > $CH_TEMPDIR/sourcedir/testfile1
pwgen > $CH_TEMPDIR/sourcedir/testfile
CH_portnum=28822
ssh-keygen -t rsa -b 1024 -N "" -h -f $CH_TEMPDIR/my_host_key > /dev/null 2>&1 
/usr/sbin/sshd -o PidFile=$CH_TEMPDIR/sshd.pid -o HostKey=$CH_TEMPDIR/my_host_key -p $CH_portnum > /dev/null 2>&1 
cleanup_peer()
{
    echo "Cleaning up..."
    kill -9 `cat $CH_TEMPDIR/sshd.pid`
    rm -rf $CH_TEMPDIR
    unalias juju-log
    unalias relation-set
    unalias relation-get
    unalias unit-get
    unalias relation-list
}
trap cleanup_peer EXIT

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
#save authorized keys and known_hosts before modifications
touch $HOME/.ssh/authorized_keys
cp $HOME/.ssh/authorized_keys $HOME/.ssh/authorized_keys_saved
touch $HOME/.ssh/known_hosts
cp $HOME/.ssh/known_hosts $HOME/.ssh/known_hosts_saved
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2"  
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    ch_peer_scp -r -p $CH_portnum -o "-q" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    ch_peer_scp -r -p $CH_portnum -o "-q" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
done
[ ! -e $CH_TEMPDIR/destdir/ ] && echo "dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && echo "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && echo "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && echo "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
#restore authorized_keys & known_hosts
mv $HOME/.ssh/authorized_keys_saved $HOME/.ssh/authorized_keys
mv $HOME/.ssh/known_hosts_saved $HOME/.ssh/known_hosts
echo PASS

start_test "ch_peer_rsync..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
#save authorized keys and known_hosts before modifications
touch $HOME/.ssh/authorized_keys
cp $HOME/.ssh/authorized_keys $HOME/.ssh/authorized_keys_saved
touch $HOME/.ssh/known_hosts
cp $HOME/.ssh/known_hosts $HOME/.ssh/known_hosts_saved
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2"  
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
    #master relation joined
    JUJU_UNIT_NAME="TEST/1"  
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    ch_peer_rsync -p $CH_portnum -o "-azq" "$CH_TEMPDIR/sourcedir/*" "$CH_TEMPDIR/destdir/" > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
done
[ ! -e $CH_TEMPDIR/destdir/ ] && echo "dir not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile0 ] && echo "file1 not copied" && exit 1
[ ! -e $CH_TEMPDIR/destdir/testfile1 ] && echo "file2 not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile0 | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile0 | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && echo "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
#restore authorized_keys & known_hosts
mv $HOME/.ssh/authorized_keys_saved $HOME/.ssh/authorized_keys
mv $HOME/.ssh/known_hosts_saved $HOME/.ssh/known_hosts
echo PASS

start_test "ch_peer_scp..."
CH_scp_hostname=""
CH_scp_ssh_key_saved=""
CH_scp_ssh_key=""
CH_scp_copy_done=""
#save authorized keys and known_hosts before modifications
touch $HOME/.ssh/authorized_keys
cp $HOME/.ssh/authorized_keys $HOME/.ssh/authorized_keys_saved
touch $HOME/.ssh/known_hosts
cp $HOME/.ssh/known_hosts $HOME/.ssh/known_hosts_saved
for i in 1 2 3 
do
    #slave relation joined
    JUJU_UNIT_NAME="TEST/2" 
    JUJU_REMOTE_UNIT="TEST/1"
    CH_MASTER=0
    ch_peer_scp -p $CH_portnum -o "-q" $CH_TEMPDIR/sourcedir/testfile $CH_TEMPDIR/destdir/ > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
    #master relation joined
    JUJU_UNIT_NAME="TEST/1" 
    JUJU_REMOTE_UNIT="TEST/2"
    CH_MASTER=1
    ch_peer_scp -p $CH_portnum -o "-q" $CH_TEMPDIR/sourcedir/testfile $CH_TEMPDIR/destdir/ > $CH_TEMPDIR/result 2> /dev/null
    [ `cat $CH_TEMPDIR/result` = 1 ] && break
done
[ ! -e $CH_TEMPDIR/destdir/testfile ] && echo "file not copied" && exit 1
CH_t1=`md5sum $CH_TEMPDIR/sourcedir/testfile | cut -d" " -f1`
CH_t2=`md5sum $CH_TEMPDIR/destdir/testfile | cut -d" " -f1`
[ ! "$CH_t1" = "$CH_t2" ] && echo "md5sum differ" && exit 1
rm -rf $CH_TEMPDIR/destdir/*
#restore authorized_keys & known_hosts
mv $HOME/.ssh/authorized_keys_saved $HOME/.ssh/authorized_keys
mv $HOME/.ssh/known_hosts_saved $HOME/.ssh/known_hosts
echo PASS
