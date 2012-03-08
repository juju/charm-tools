#!/usr/bin/python

import signal,os,sys

signal.alarm(60)
os.execv(sys.argv[1],sys.argv[1:])
