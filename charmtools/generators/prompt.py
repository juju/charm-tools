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


def get_validator(type_):
    return {
        'str': str,
        'string': str,
        'int': int,
        'integer': int,
        'float': float,
        'bool': boolean_validator,
        'boolean': boolean_validator,
    }[type_]


def boolean_validator(s):
    return s and s.lower() == 'true' or s.lower()[0] == 'y'


class PromptList(list):
    def __init__(self, prompt_dicts=None):
        prompts = []
        for k, v in (prompt_dicts or {}).items():
            prompts.append(Prompt(
                k,
                v['prompt'],
                v['default'],
                v.get('type', 'string'),
            ))
        super(PromptList, self).__init__(prompts)


class Prompt(object):
    def __init__(self, name, prompt, default, type_='string'):
        self.name = name
        self.prompt = prompt.strip() + ' '
        self.default = default
        self.type_ = type_

    def validate(self, value):
        """Return the (possibly modified) validated value, or raise an
        Exception with a message explaining why the value is invalid.

        """
        return get_validator(self.type_)(value)
