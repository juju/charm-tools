#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import sys
import ez_setup


ez_setup.use_setuptools()

from setuptools import setup, find_packages

__version__ = '1.1.0-rc2'


setup(
    name='charmtools',
    version=__version__,
    packages=['charmtools'],
    install_requires=['launchpadlib', 'argparse', 'cheetah', 'pyyaml',
                      'pycrypto', 'paramiko', 'bzr'],
    package_data={'charmtools': ['templates/*/*.*', 'templates/*/hooks/*']},
    maintainer='Marco Ceppi',
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
            'charm = charmtools:main',
            'juju-charm = charmtools:main',
            'charm-get = charmtools.get:main',
            'charm-getall = charmtools.getall:main',
            'charm-proof = charmtools.proof:main',
            'charm-create = charmtools.create:main',
            'charm-list = charmtools.list:main',
            'charm-promulgate = charmtools.promulgate:main',
            'charm-review = charmtools.review:main',
            'charm-review-queue = charmtools.review_queue:main',
            'charm-search = charmtools.search:main',
            'charm-subscribers = charmtools.subscribers:main',
            'charm-unpromulgate = charmtools.unpromulgate:main',
            'charm-update = charmtools.update:main',
        ],
    },
)
