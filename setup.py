#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import sys
import ez_setup


ez_setup.use_setuptools()

from setuptools import setup, find_packages

__version__ = {
  'charmhelpers': '0.0.3',
  'charm-tools': '0.1.0'
}


if 'charm-tools' not in sys.argv[0]: 
    setup(
        name='charmhelpers',
        version=__version__['charmhelpers'],
        packages=find_packages('helpers/python'),
        package_dir={'': 'helpers/python'},
        include_package_data=True,
        zip_safe=False,
        maintainer='Launchpad Yellow',
        description=('Helper functions for writing Juju charms'),
        license='GPL v3',
        url='https://launchpad.net/charm-tools',
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "Programming Language :: Python",
        ],
    )
else:
    setup(
        name='charmtools',
        version=__version__['charm-tools'],
        packages=['charmtools'],
        install_requires=['launchpadlib'],
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
                'juju-charm = charmtools:main',
                'juju-charm-get = charmtools.get:main',
                'juju-charm-getall = charmtools.getall:main',
                'juju-charm-proof = charmtools.proof:main',
                'juju-charm-create = charmtools.create:main',
                'juju-charm-list = charmtools.list:main',
                'juju-charm-promulgate = charmtools.promulgate:main',
                'juju-charm-review = charmtools.review:main',
                'juju-charm-review-queue = charmtools.review_queue:main',
                'juju-charm-search = charmtools.search:main',
                'juju-charm-subscribers = charmtools.subscribers:main',
                'juju-charm-unpromulgate = charmtools.unpromulgate:main',
                'juju-charm-update = charmtools.update:main',
            ],
        },
    )
