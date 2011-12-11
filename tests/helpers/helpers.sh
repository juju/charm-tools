#!/bin/sh

set -ue

test_home=`dirname $0`
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

if [ "$MOCK_NET" = "true" ] ; then
    alias host=mock_host
    alias dig=mock_dig    
fi

. $HELPERS_SOURCE

echo -n Testing ch_type_hash...
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

echo -n Testing ch_is_url...
ch_is_url "not a url" && return 1 || :
ch_is_url "http://www.w3c.org/" > /dev/null
ch_is_url "ftp://ftp.kernel.org/" > /dev/null
ch_is_url "https://launchpad.net" > /dev/null
[ "`ch_is_url 'https://launchpad.net'`" = "true" ]
echo PASS

echo -n Testing ch_is_ip...
ch_is_ip 'just.a.hostname.com' && return 1 || :
ch_is_ip '256.2.3.4' && return 1 || :
ch_is_ip '1.2.3.4' > /dev/null
ch_is_ip '192.168.3.4' > /dev/null
[ "`ch_is_ip '192.168.3.4'`" = "true" ]
echo PASS

echo -n Testing ch_get_ip...
testhostname=launchpad.net
myip=`host -t A $testhostname|head -n 1|cut -d' ' -f4`
ch_get_ip _invalid#hostname > /dev/null && return 1 || :
ch_get_ip $testhostname > /dev/null
[ "`ch_get_ip $testhostname`" = "$myip" ]
echo PASS

temp_dir=""
cleanup_temp () {
    [ -n "$temp_dir" ] || return 0
    # Trying to be safe, only one level of files should be there
    if [ -f "$temp_dir/webserver.pid" ] ; then
        webserver_pid=`cat $temp_dir/webserver.pid`
        if [ -n "$webserver_pid" ] ; then
            echo -n Shutting down webserver...
            kill $webserver_pid || echo -n webserver already dead?...
            wait
            echo DONE
        fi
    fi
    rm -f $temp_dir/*
    rmdir $temp_dir
}

trap cleanup_temp EXIT

temp_dir=`mktemp -d /tmp/charm-helper-tests.XXXXXX`
save_pwd=$PWD
cd $temp_dir
echo Starting SimpleHTTPServer in $PWD on port 8999 to test fetching files...
$test_home/run_webserver.sh 8999 > /dev/null 2>&1 &
echo Giving it 1 second to start
sleep 1
echo Creating temp data file
cat > testdata.txt <<EOF
The quick brown fox jumped over the lazy brown dog.
EOF
text_hash=`md5sum testdata.txt|cut -d' ' -f1`
echo creating gzipped test data
gzip -c testdata.txt > testdata.txt.gz
gzip_hash=`sha256sum testdata.txt.gz|cut -d' ' -f1`
cd $save_pwd
test_url=http://127.0.0.1:8999
echo -n Testing ch_get_file...
ch_get_file _bad_#args/foo && return 1 || :
ch_get_file $test_url/testdata.txt
ch_get_file $test_url/testdata.txt $text_hash
ch_get_file $test_url/testdata.txt.gz
ch_get_file $test_url/testdata.txt.gz $gzip_hash
echo PASS
