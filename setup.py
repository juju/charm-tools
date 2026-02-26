#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import os
import re
import subprocess
from setuptools import setup, find_packages


curdir = os.path.dirname(__file__)
version_cache = os.path.join(curdir, 'charmtools', 'VERSION')
try:
    version = subprocess.check_output(
        ['git', 'describe', '--tags', '--always'],
        cwd=curdir, stderr=subprocess.DEVNULL
    ).decode('UTF-8').strip().lstrip('v')
except Exception:
    version = 'unknown'
# Convert git describe to PEP 440: e.g. '3.0.8-12-gea043cd' -> '3.0.8.post12+gea043cd'
m = re.match(r'^(\d+\.\d+\.\d+)-(\d+)-g(.+)$', version)
if m:
    version = '{}.post{}+g{}'.format(m.group(1), m.group(2), m.group(3))
elif not re.match(r'^\d+\.\d+', version):
    # Bare commit hash or non-semver string — treat as unknown
    version = 'unknown'
if version == 'unknown':
    # during install; use cached VERSION
    try:
        with open(version_cache, 'r') as fh:
            version = fh.read().strip()
    except Exception:
        version = None
else:
    # during build; update cached VERSION
    with open(version_cache, 'w') as fh:
        fh.write(version)

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as fh:
    readme = fh.read()


setup(
    name='charm-tools',
    version=version,
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=[
        'cheetah3>=3.0.0,<4.0',
        'pyyaml>=5.0,!=5.4.0,!=5.4.1,!=6.0,<7.0',
        'requests>=2.0.0,<3.0.0',
        'blessings<2.0',
        'ruamel.yaml<0.16.0;python_version < "3.7"',
        'pathspec<=0.3.4;python_version < "3.7"',
        'ruamel.yaml<0.18;python_version >= "3.7"',
        'pathspec<0.11;python_version >= "3.7"',
        'otherstuf<=1.1.0',
        'path<17',
        'pip>=1.5.4',
        'jujubundlelib<0.6',
        'virtualenv>=1.11.4,<21',
        'colander<1.9',
        'jsonschema<4.18.0',
        'keyring<24',
        'secretstorage<3.4',
        'dict2colander==0.2',
        'requirements-parser<0.6',
        'setuptools<82.0',
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
