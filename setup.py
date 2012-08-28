#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import ez_setup


ez_setup.use_setuptools()

from setuptools import setup, find_packages

__version__ = '0.0.1'


setup(
    name='charmhelpers',
    version=__version__,
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
