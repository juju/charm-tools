from __future__ import absolute_import

import glob
import os
import re
import yaml

import jujubundlelib.validation
from charmtools.utils import validate_display_name

from charmtools.linter import Linter


charm_url_includes_id = re.compile(r'-\d+$').search


class BundleLinter(Linter):
    def validate(self, data):
        """Supplement jujubundlelib validation with some extra checks.

        """
        validate_display_name(data, self)
        if 'series' not in data and 'inherits' not in data:
            self.info("No series defined")

        if 'services' in data:
            app_key = 'services'
        else:
            app_key = 'applications'

        if app_key in data:
            for svc, sdata in data[app_key].items():
                if 'annotations' not in sdata:
                    self.warn('%s: No annotations found, will render '
                              'poorly in GUI' % svc)
                if ('charm' in sdata and
                        not charm_url_includes_id(sdata['charm'] or '')):
                    self.warn(
                        '%s: charm URL should include a revision' % svc)
        else:
            if 'inherits' not in data:
                self.err("No applications defined")

    def proof(self, bundle):
        data = bundle.bundle_file()
        if not bundle.is_v4(data):
            self.err(
                'This bundle format is no longer supported. See '
                'https://jujucharms.com/docs/stable/charms-bundles '
                'for the supported format.')
            return

        readmes = glob.glob(os.path.join(bundle.bundle_path, 'README*'))
        if len(readmes) < 1:
            self.warn('No readme file found')

        errors = jujubundlelib.validation.validate(data)
        for error in errors:
            self.err(error)
        self.validate(data)


class Bundle(object):
    def __init__(self, path, debug=False):
        self.bundle_path = os.path.abspath(path)
        self.supported_files = [
            'bundle.yaml'
        ]
        self.debug = debug
        if not self.is_bundle():
            raise Exception('Not a bundle')

    def is_bundle(self):
        for f in self.supported_files:
            if os.path.isfile(os.path.join(self.bundle_path, f)):
                break
        else:
            return False

        if os.path.isfile(os.path.join(self.bundle_path, 'metadata.yaml')):
            return False

        return True

    def is_v4(self, data=None):
        if data is None:
            data = self.bundle_file()
        v4_keys = {'applications', 'services', 'relations', 'machines', 'series'}
        bundle_keys = set(data.keys())
        return bool(v4_keys & bundle_keys)

    def bundle_file(self, parse=True):
        for f in self.supported_files:
            if os.path.isfile(os.path.join(self.bundle_path, f)):
                with open(os.path.join(self.bundle_path, f)) as d:
                    return yaml.safe_load(d.read()) if parse else d.read()

        raise Exception('No bundle.json or bundle.yaml file found')

    def proof(self):
        lint = BundleLinter(self.debug)
        lint.proof(self)
        return lint.lint, lint.exit_code

    def promulgate(self):
        pass
