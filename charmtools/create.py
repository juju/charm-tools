#!/usr/bin/python
#
#    create - generate Juju charm from template
#
#    Copyright (C) 2011  Canonical Ltd.
#    Author: Clint Byrum <clint.byrum@canonical.com>
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

import os
import sys
import os.path as path
import time
import shutil
import tempfile
import textwrap
import socket
import argparse

from Cheetah.Template import Template
from stat import ST_MODE


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


def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('charmname', help='Name of charm to create.')
    parser.add_argument('charmhome', nargs='?',
                        help='Dir to create charm in. Defaults to CHARM_HOME '
                        'env var or PWD')

    return parser


def apt_fill(package):
    v = {}
    try:
        import apt
        c = apt.Cache()
        c.open()
        p = c[package]
        print "Found " + package + " package in apt cache, as a result charm" \
              + " contents have been pre-populated based on package metadata."

        v['summary'] = p.summary
        v['description'] = textwrap.fill(p.description, width=72,
                                         subsequent_indent='  ')
    except:
        print "Failed to find " + package + " in apt cache, creating " \
            + "an empty charm instead."
        v['summary'] = '<Fill in summary here>'
        v['description'] = '<Multi-line description here>'

    return v


def main():
    parser = setup_parser()
    args = parser.parse_args()

    try:
        from ubuntutools.config import ubu_email as get_maintainer
    except ImportError:
        get_maintainer = portable_get_maintainer

    if args.charmhome:
        charm_home = args.charmhome
    else:
        charm_home = os.getenv('CHARM_HOME', '.')

    home = path.abspath(path.dirname(__file__))
    template_dir = path.join(home, 'templates')
    output_dir = path.join(charm_home, args.charmname)
    print "Generating template for " + args.charmname + " from templates in " \
        + template_dir
    print "Charm will be stored in " + output_dir

    if path.exists(output_dir):
        print output_dir + " exists. Please move it out of the way."
        sys.exit(1)

    shutil.copytree(path.join(template_dir, 'charm'), output_dir)

    v = {'package': args.charmname,
         'maintainer': '%s <%s>' % get_maintainer()}

    v.update(apt_fill(args.charmname))

    ignore_parsing = ['README.ex']

    for root, dirs, files in os.walk(output_dir):
        for outfile in files:
            full_outfile = path.join(root, outfile)
            mode = os.stat(full_outfile)[ST_MODE]
            if outfile in ignore_parsing:
                continue

            try:
                t = Template(file=full_outfile, searchList=(v))
                o = tempfile.NamedTemporaryFile(dir=root, delete=False)
                os.chmod(o.name, mode)
                o.write(str(t))
                o.close()
                backupname = full_outfile + str(time.time())
                os.rename(full_outfile, backupname)
                try:
                    os.rename(o.name, full_outfile)
                    os.unlink(backupname)
                except Exception, e:
                    print "WARNING: Could not enable templated file: " + str(e)
                    os.rename(backupname, full_outfile)
                    raise
            except Exception, e:
                print "WARNING: could not process template for " \
                    + full_outfile + ": " + str(e)
                raise

if __name__ == "__main__":
    main()
