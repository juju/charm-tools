# Copyright 2014-2015 Canonical Limited.
#
# This file is part of charm-helpers.
#
# charm-helpers is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# charm-helpers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with charm-helpers.  If not, see <http://www.gnu.org/licenses/>.


import inspect

from docutils.parsers.rst import directives
from sphinx.ext.autosummary import Autosummary
from sphinx.ext.autosummary import get_import_prefixes_from_env
from sphinx.ext.autosummary import import_by_name


class AutoMemberSummary(Autosummary):
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = {
        'toctree': directives.unchanged,
        'nosignatures': directives.flag,
        'template': directives.unchanged,
    }

    def get_items(self, names):
        env = self.state.document.settings.env
        prefixes = get_import_prefixes_from_env(env)

        items = []
        prefix = ''
        shorten = ''

        def _get_items(name):
            _items = super(AutoMemberSummary, self).get_items([shorten + name])
            if self.result.data and ".. deprecated::" in self.result.data[0]:
                # don't show deprecated classes / functions in summary
                return
            for dn, sig, summary, rn in _items:
                if ".. deprecated::" in summary:
                    # don't show deprecated methods in summary
                    continue
                items.append(('%s%s' % (prefix, dn), sig, summary, rn))

        for name in names:
            if '~' in name:
                prefix, name = name.split('~')
                shorten = '~'
            else:
                prefix = ''
                shorten = ''

            try:
                real_name, obj, parent, _ = import_by_name(name, prefixes=prefixes)
            except ImportError:
                self.warn('failed to import %s' % name)
                continue

            if not inspect.ismodule(obj):
                _get_items(name)
                continue

            for member in dir(obj):
                if member.startswith('_'):
                    continue
                mobj = getattr(obj, member)
                if hasattr(mobj, '__module__'):
                    if not mobj.__module__.startswith(real_name):
                        continue  # skip imported classes & functions
                elif hasattr(mobj, '__name__'):
                    continue  # skip imported modules
                else:
                    continue  # skip instances
                _get_items('%s.%s' % (mobj.__module__, member))

        return items


def setup(app):
    app.add_directive('automembersummary', AutoMemberSummary)
