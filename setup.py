#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import os
import subprocess
import sys
import json
from setuptools import setup


curdir = os.path.dirname(__file__)
version_cache = os.path.join(curdir, 'charmtools', 'VERSION')
try:
    version_raw = subprocess.check_output(['vergit', '--format=json']).strip()
    if sys.version_info >= (3, 0):
        version_raw = version_raw.decode('UTF-8')
    version = json.loads(version_raw)['version']
except Exception:
    version = 'unknown'
if version == 'unknown':
    # during install; use cached VERSION
    try:
        with open(version_cache, 'r') as fh:
            version_raw = fh.read()
        version = json.loads(version_raw)['version']
    except Exception:
        version = None
else:
    # during build; update cached VERSION
    with open(version_cache, 'w') as fh:
        fh.write(version_raw)


setup(
    version=version,
)
