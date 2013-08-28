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
        name='charm-tools',
        version=__version__['charm-tools'],
        packages=['charm-tools'],
        install_requires=["launchpadlib"],
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
                'juju-charm = charm-tools:main',
                'juju-charm-get = charm-tools.get:main',
                'juju-charm-getall = charm-tools.getall:main',
                'juju-charm-proof = charm-tools.proof:main',
                'juju-charm-create = charm-tools.create:main',
                'juju-charm-list = charm-tools.list:main',
                'juju-charm-promulgate = charm-tools.promulgate:main',
                'juju-charm-review = charm-tools.review:main',
                'juju-charm-review-queue = charm-tools.review_queue:main',
                'juju-charm-search = charm-tools.search:main',
                'juju-charm-subscribers = charm-tools.subscribers:main',
                'juju-charm-unpromulgate = charm-tools.unpromulgate:main',
                'juju-charm-update = charm-tools.update:main',
            ],
        },
    )
