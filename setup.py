#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import os
import subprocess
import sys
import json
from setuptools import setup, find_packages


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

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as fh:
    readme = fh.read()


setup(
    name='charm-tools',
    version=version,
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=[
        'launchpadlib<1.11',
        'cheetah3>=3.0.0',
        'pyyaml>=5.0,!=5.4.0,!=5.4.1,<6.0',
        'requests>=2.0.0,<3.0.0',
        'libcharmstore',
        # macaroonbakery is pulled in by libcharmstore->theblues, v1.3.4 added
        # a constraint of protobuf>=3.20.0[0] which makes it incompatible with
        # python 3.6 while v1.3.3 was released in a broken state[1]
        #
        # [0] https://github.com/go-macaroon-bakery/py-macaroon-bakery/commit/7f1fe6a2adb2f80db12bccfb81f629d66d106e03  # noqa
        # [1] https://github.com/go-macaroon-bakery/py-macaroon-bakery/pull/92
        'macaroonbakery < 1.3.3;python_version < "3.7"',
        'blessings',
        'ruamel.yaml<0.16.0;python_version < "3.7"',
        'pathspec<=0.3.4;python_version < "3.7"',
        'ruamel.yaml<0.18;python_version >= "3.7"',
        'pathspec;python_version >= "3.7"',
        'otherstuf<=1.1.0',
        'path.py>=10.5',
        'pip>=1.5.4',
        'jujubundlelib',
        'virtualenv>=1.11.4',
        'colander<=1.7.0',
        'jsonschema<=2.5.1',
        'keyring<21',
        'secretstorage<2.4',
        'dict2colander==0.2',
        'vergit>=1.0.0,<2.0.0',
        'requirements-parser',
    ],
    include_package_data=True,
    maintainer='Cory Johns',
    maintainer_email='johnsca@gmail.com',
    description=('Tools for building and maintaining Juju charms'),
    long_description=readme,
    license='GPL v3',
    url='https://github.com/juju/charm-tools',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
    ],
    entry_points={
        'console_scripts': [
            'charm-add = charmtools.generate:main',
            'charm-build = charmtools.build.builder:main',
            'charm-create = charmtools.create:main',
            'charm-help = charmtools.cli:usage',
            'charm-layers = charmtools.build.builder:inspect',
            'charm-proof = charmtools.proof:main',
            'charm-pull-source = charmtools.pullsource:main',
            'charm-version = charmtools.version:main',
            'charm-promulgate = charmtools.promulgation:promulgate',
            'charm-unpromulgate = charmtools.promulgation:unpromulgate',
        ],
        'charmtools.templates': [
            'bash = charmtools.templates.bash:BashCharmTemplate',
            'reactive-python = charmtools.templates.reactive_python:ReactivePythonCharmTemplate',  # noqa: E501
            'reactive-bash = charmtools.templates.reactive_bash:ReactiveBashCharmTemplate',  # noqa: E501
            'python-basic = charmtools.templates.python:PythonCharmTemplate',
            'python = charmtools.templates.python_services:PythonServicesCharmTemplate',  # noqa: E501
            'ansible = charmtools.templates.ansible:AnsibleCharmTemplate',
            'chef = charmtools.templates.chef:ChefCharmTemplate',
            'powershell = charmtools.templates.powershell:PowerShellCharmTemplate',  # noqa: E501
        ]
    },
)
