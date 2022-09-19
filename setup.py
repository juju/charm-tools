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
        'cheetah3>=3.0.0,<4.0',
        'pyyaml>=5.0,<6.0',
        'requests>=2.0.0,<3.0.0',
        'blessings<2.0',
        'ruamel.yaml<0.16.0;python_version < "3.7"',
        'pathspec<=0.3.4;python_version < "3.7"',
        'ruamel.yaml<0.18;python_version >= "3.7"',
        'pathspec<0.11;python_version >= "3.7"',
        'otherstuf<=1.1.0',
        'path.py>=10.5,<13',
        'pip>=1.5.4<23',
        'jujubundlelib<0.6',
        'virtualenv>=1.11.4,<21',
        'colander<1.9',
        'jsonschema<5.0',
        'keyring<24',
        'secretstorage<3.4',
        'dict2colander==0.2',
        'vergit>=1.0.0,<2.0.0',
        'requirements-parser<0.6',
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
            'charm-build = charmtools.build.builder:main',
            'charm-create = charmtools.create:main',
            'charm-help = charmtools.cli:usage',
            'charm-layers = charmtools.build.builder:inspect',
            'charm-proof = charmtools.proof:main',
            'charm-pull-source = charmtools.pullsource:main',
            'charm-version = charmtools.version:main',
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
