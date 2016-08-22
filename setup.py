#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

from setuptools import setup, find_packages


setup(
    name='charm-tools',
    version="2.1.4",
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=['launchpadlib', 'argparse', 'cheetah', 'pyyaml',
                      'pycrypto', 'paramiko<2.0.0', 'requests',
                      'libcharmstore', 'blessings', 'ruamel.yaml',
                      'pathspec', 'otherstuf', 'path.py', 'pip',
                      'jujubundlelib', 'virtualenv', 'colander',
                      'jsonschema', 'secretstorage<2.3.0'],
    include_package_data=True,
    maintainer='Marco Ceppi',
    maintainer_email='marco@ceppi.net',
    description=('Tools for maintaining Juju charms'),
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
            'charm-test = charmtools.test:main',
            'charm-version = charmtools.version:main',
            'juju-test = charmtools.test:main',
        ],
        'charmtools.templates': [
            'bash = charmtools.templates.bash:BashCharmTemplate',
            'reactive-python = charmtools.templates.reactive_python:ReactivePythonCharmTemplate',
            'reactive-bash = charmtools.templates.reactive_bash:ReactiveBashCharmTemplate',
            'python-basic = charmtools.templates.python:PythonCharmTemplate',
            'python = charmtools.templates.python_services'
            ':PythonServicesCharmTemplate',
            'ansible = charmtools.templates.ansible:AnsibleCharmTemplate',
            'chef = charmtools.templates.chef:ChefCharmTemplate',
            'powershell = '
                'charmtools.templates.powershell:PowerShellCharmTemplate',
        ]
    },
)
