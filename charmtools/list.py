#!/usr/bin/env python
# Copyright (C) 2013 Marco Ceppi <marco@ceppi.net>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
from . import charms


def main():
    if len(sys.argv) > 1:
        print('usage: list [ --help ]')
        if sys.argv[1] == '--help':
            sys.exit(0)
        else:
            sys.exit(1)

    print "\n".join(charms.remote())


if __name__ == "__main__":
    main()
