#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

from setuptools import setup, find_packages


setup(
    name='charm-tools',
    version="1.7.1",
    packages=find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=['launchpadlib', 'argparse', 'cheetah', 'pyyaml',
                      'pycrypto', 'paramiko', 'bzr', 'requests',
                      'charmworldlib', 'blessings', 'ruamel.yaml',
                      'pathspec', 'otherstuf', "path.py",
                      "jujubundlelib"],
    include_package_data=True,
    maintainer='Marco Ceppi',
    maintainer_email='marco@ceppi.net',
    description=('Tools for maintaining Juju charms'),
    license='GPL v3',
    url='https://launchpad.net/charm-tools',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
    ],
    entry_points={
        'console_scripts': [
            'charm = charmtools:charm',
            'charm-add = charmtools.generate:main',
            'charm-compose = charmtools.compose:main',
            'charm-create = charmtools.create:main',
            'charm-generate = charmtools.compose:main',
            'charm-get = charmtools.get:main',
            'charm-getall = charmtools.getall:main',
            'charm-help = charmtools.cli:usage',
            'charm-info = charmtools.info:main',
            'charm-layers = charmtools.compose:inspect',
            'charm-list = charmtools.list:main',
            'charm-promulgate = charmtools.promulgate:main',
            'charm-proof = charmtools.proof:main',
            'charm-refresh = charmtools.compose:main',
            'charm-review = charmtools.review:main',
            'charm-review-queue = charmtools.review_queue:main',
            'charm-search = charmtools.search:main',
            'charm-subscribers = charmtools.subscribers:main',
            'charm-test = charmtools.test:main',
            'charm-unpromulgate = charmtools.unpromulgate:main',
            'charm-update = charmtools.update:main',
            'charm-version = charmtools.version:main',
            'juju-bundle = charmtools:bundle',
            'juju-charm = charmtools:charm',
            'juju-test = charmtools.test:main',
        ],
        'charmtools.templates': [
            'bash = charmtools.templates.bash:BashCharmTemplate',
            'python-basic = charmtools.templates.python:PythonCharmTemplate',
            'python = charmtools.templates.python_services'
            ':PythonServicesCharmTemplate',
            'ansible = charmtools.templates.ansible:AnsibleCharmTemplate',
            'chef = charmtools.templates.chef:ChefCharmTemplate'
        ]
    },
)
