#!/usr/bin/python

#    Copyright (C) 2014  Canonical Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import socket
import textwrap

import pkg_resources

log = logging.getLogger(__name__)


def get_installed_templates():
    for ep in pkg_resources.iter_entry_points('charmtools.templates'):
        yield ep.name


def apt_fill(package):
    v = {}
    try:
        import apt
        c = apt.Cache()
        c.open()
        p = c[package]
        log.info(
            "Found %s in apt cache; charm contents have been pre-populated "
            "from package metadata.", package)

        # summary and description attrs moved to Version
        # object in python-apt 0.7.9
        if not hasattr(p, 'summary'):
            p = p.versions[0]

        v['summary'] = p.summary
        v['description'] = textwrap.fill(p.description, width=72,
                                         subsequent_indent='  ')
    except:
        log.info(
            "No %s in apt cache; creating an empty charm instead.", package)
        v['summary'] = '<Fill in summary here>'
        v['description'] = '<Multi-line description here>'

    return v


def portable_get_maintainer():
    """ Portable best effort to determine a maintainer """
    if 'NAME' in os.environ:
        name = os.environ['NAME']
    else:
        try:
            import pwd
            name = pwd.getpwuid(os.getuid()).pw_gecos.split(',')[0].strip()

            if not len(name):
                name = pwd.getpwuid(os.getuid())[0]
        except:
            name = 'Your Name'

    if not len(name):
        name = 'Your Name'

    email = os.environ.get('EMAIL', '%s@%s' % (name.replace(' ', '.'),
                                               socket.getfqdn()))
    return name, email
