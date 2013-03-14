#!/usr/bin/python

import os
import sys
import signal

signal.alarm(60)
os.execv(sys.argv[1], sys.argv[1:])
