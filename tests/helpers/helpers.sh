#!/bin/sh

set -ue

test_home=`dirname $0`
test_home=`readlink -f $test_home`

# Should set 60 second timeout
if [ -z ${1:-""} ] ; then
    exec $test_home/run_with_timeout.py $0 timeout
fi

HELPERS_SOURCE=${HELPERS_SOURCE:-"$test_home/../../helpers/sh/net.sh"}
MOCK_NET=${MOCK_NET:-"true"}

mock_host () {
    if echo $* | grep -q "[_#]" ; then return 1 ; fi
    echo nothost.local has address 127.0.0.1
    echo nothost.local has address 127.0.1.1
}

mock_dig () {
    if echo $* | grep -q "[_#]" ; then return 1 ; fi
    echo 127.0.0.1
    echo 127.0.1.1
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

if [ "$MOCK_NET" = "true" ] ; then
    alias host=mock_host
    alias dig=mock_dig    
fi

# Uncomment this to get more info on why wget failed
#CH_WGET_ARGS="--verbose"

. $HELPERS_SOURCE

start_test ch_type_hash...
# Test return codes
ch_type_hash "not a hash" > /dev/null && return 1 || :
ch_type_hash '062b92a381b6ee8f87917f8dc19ff1bb' > /dev/null
ch_type_hash '188c481c99311aba88ffeadde1d59fcca3d64d10' > /dev/null
ch_type_hash '07a9a2188113d45f23e4abe3e8b540931d1f3892634399688bab4bde08132b4b' > /dev/null
# Test types
[ "`ch_type_hash '062b92a381b6ee8f87917f8dc19ff1bb'`" = "md5" ]
[ "`ch_type_hash '188c481c99311aba88ffeadde1d59fcca3d64d10'`" = "sha1" ]
[ "`ch_type_hash '07a9a2188113d45f23e4abe3e8b540931d1f3892634399688bab4bde08132b4b'`" = "sha256" ]
echo PASS

start_test ch_is_url...
ch_is_url "not a url" && return 1 || :
ch_is_url "http://www.w3c.org/" > /dev/null
ch_is_url "ftp://ftp.kernel.org/" > /dev/null
ch_is_url "https://launchpad.net" > /dev/null
[ "`ch_is_url 'https://launchpad.net'`" = "true" ]
echo PASS

start_test Testing ch_is_ip...
ch_is_ip 'just.a.hostname.com' && return 1 || :
ch_is_ip '256.2.3.4' && return 1 || :
ch_is_ip '1.2.3.4' > /dev/null
ch_is_ip '192.168.3.4' > /dev/null
ch_is_ip '3.1.1.1' > /dev/null
[ "`ch_is_ip '192.168.3.4'`" = "true" ]
echo PASS

start_test Testing ch_get_ip...
testhostname=launchpad.net
myip=`host -t A $testhostname|head -n 1|cut -d' ' -f4`
ch_get_ip _invalid#hostname > /dev/null && return 1 || :
ch_get_ip $testhostname > /dev/null
[ "`ch_get_ip $testhostname`" = "$myip" ]
echo PASS

save_pwd=$PWD
temp_srv_dir=""
temp_dl_dir=""
temp_dirs=""
cleanup_temp () {
    if [ -n "$temp_dirs" ] ; then
        # Trying to be safe, only one level of files should be there
        if [ -f "$temp_srv_dir/webserver.pid" ] ; then
            webserver_pid=`cat $temp_srv_dir/webserver.pid`
            if [ -n "$webserver_pid" ] ; then
                start_output Shutting down webserver...
                kill $webserver_pid || echo -n webserver already dead?...
                wait
                echo DONE
            fi
        fi
        if [ -n "$temp_srv_dir" ] && [ -s $temp_srv_dir/server.log ] ; then
            output Printing server log
            cat $temp_srv_dir/server.log
        fi
        local dir=""
        for dir in $temp_dirs ; do
            rm -f $dir/*
            rmdir $dir
        done
    fi
    cd $save_pwd
    CH_cleanup_sshd
}

trap cleanup_temp EXIT

temp_srv_dir=`mktemp -d /tmp/charm-helper-srv.XXXXXX`
temp_dl_dir=`mktemp -d /tmp/charm-helper-dl.XXXXXX`
temp_dirs="$temp_srv_dir $temp_dl_dir"
test_url=http://127.0.0.1:8999
cd $temp_srv_dir
output Starting SimpleHTTPServer in $PWD on port 8999 to test fetching files.
sh $test_home/run_webserver.sh 8999 > $temp_srv_dir/server.log 2>&1 &
output Looping wget until webserver responds...
listening=0
for i in 1 2 3 4 5 ; do
  sleep 1
  if wget -q $test_url/ ; then
    output Attempt $i succeeded.
    listening=1
    break
  fi
  output Attempt $i failed..
done
if [ $listening -eq 0 ] ; then
    output fetching from test webserver Failed $i times, aborting.
    exit 1
fi
output Creating temp data file
cat > testdata.txt <<EOF
The quick brown fox jumped over the lazy brown dog.
EOF
text_hash=`md5sum testdata.txt|cut -d' ' -f1`
output creating gzipped test data
gzip -c testdata.txt > testdata.txt.gz
gzip_hash=`sha256sum testdata.txt.gz|cut -d' ' -f1`

cd $temp_dl_dir
CH_DOWNLOAD_DIR=$temp_dl_dir
start_test ch_get_file...
ch_get_file '_bad_#args/foo' && return 1 || :
ch_get_file $test_url/testdata.txt > /dev/null
f=`ch_get_file $test_url/testdata.txt`
cmp $f $temp_srv_dir/testdata.txt
ch_get_file $test_url/testdata.txt $text_hash > /dev/null
ch_get_file $test_url/testdata.txt.gz > /dev/null
f=`ch_get_file $test_url/testdata.txt.gz`
cmp $f $temp_srv_dir/testdata.txt.gz
ch_get_file $test_url/testdata.txt.gz $gzip_hash > /dev/null
echo PASS

start_test ch_unit_id...
JUJU_UNIT_NAME="TEST/1"
[ ! `ch_unit_id $JUJU_UNIT_NAME` -eq 1 ] && return 1
bad="badarg"
ch_unit_id $bad > /dev/null || return 1
echo PASS

start_test ch_my_unit_id...
[ ! `ch_my_unit_id` -eq  1 ] && return 1
echo PASS

start_test ch_peer_am_I_leader...
JUJU_REMOTE_UNIT="TEST/3"
JUJU_UNIT_NAME="TEST/2"
CH_MASTER=1
[ `ch_peer_am_I_leader` -eq 1 ] && return 1 || :
JUJU_UNIT_NAME="TEST/1"
[ `ch_peer_am_I_leader` -eq 1 ] || return 1 && :
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


