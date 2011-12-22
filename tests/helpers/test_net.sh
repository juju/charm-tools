#!/bin/sh

if [ -z "$test_home" ] ; then
    test_home=`dirname $0`
    test_home=`readlink -f $test_home`
fi

[ "$LIB_SOURCED" = "1" ] || . $test_home/lib.sh

set -ue

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

if [ "$MOCK_NET" = "true" ] ; then
    alias host=mock_host
    alias dig=mock_dig    
fi

# Uncomment this to get more info on why wget failed
#CH_WGET_ARGS="--verbose"

. $HELPERS_HOME/net.sh

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
#test with CH_DOWLOAD_DIR unset
unset CH_DOWNLOAD_DIR
f=`ch_get_file $test_url/testdata.txt`
cmp $f $temp_srv_dir/testdata.txt
rm $f
echo PASS

trap - EXIT
cleanup_temp
