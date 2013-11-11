#!/bin/sh
echo $$ > webserver.pid
exec python -m SimpleHTTPServer $*
