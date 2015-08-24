import glob
import json
import os
import re
import yaml

from linter import Linter
from charmworldlib import bundle as cw_bundle
import jujubundlelib.validation


charm_url_includes_id = re.compile(r'-\d+$').search


class BundleLinter(Linter):
    def validate(self, data, name=None):
        """Validate the bundle.

        Tests:
          * No series set and not inheriting,
          * Position annotations give for each service.
        """
        leader = '%s: ' % name if name else ''
        if 'series' not in data and 'inherits' not in data:
            self.info("%sNo series defined" % leader)

        if 'services' in data:
            for svc, sdata in data['services'].items():
                if 'annotations' not in sdata:
                    self.warn('%s%s: No annotations found, will render '
                              'poorly in GUI' % (leader, svc))
                if not charm_url_includes_id(sdata['charm']):
                    self.warn(
                        '%s%s: charm URL should include a revision' % (
                            leader, svc))

        else:
            if 'inherits' not in data:
                self.err("%sNo services defined" % leader)
                return

    def local_proof(self, bundle):
        data = bundle.bundle_file()

        readmes = glob.glob(os.path.join(bundle.bundle_path, 'README*'))
        if len(readmes) < 1:
            self.warn('No readme file found')

        if bundle.is_v4(data):
            self.validate(data)
        else:
            for name, bdata in data.items():
                if name == 'envExport':
                    self.warn('envExport is the default export name. Please '
                              'use a unique name')
                self.validate(bdata, name)

    def remote_proof(self, bundle, server, port, secure):
        data = bundle.bundle_file()
        if bundle.is_v4(data):
            # use jujubundlelib in lieu of deprecated API
            errors = jujubundlelib.validation.validate(data)
            for error in errors:
                self.err(error)
            return

        if server is not None or port is not None:
            # Use the user-specified overrides for the remote server.
            bundles = cw_bundle.Bundles(server=server, port=port,
                                        secure=secure)
        else:
            # Otherwise use the defaults.
            bundles = cw_bundle.Bundles()

        proof_output = bundles.proof(data)

        if self.debug:
            print json.dumps(proof_output, 2)

        for key, emitter in (('error_messages', self.err),
                             ('warning_messages', self.warn)):
            if key in proof_output:
                for message in proof_output[key]:
                    emitter(message)


class Bundle(object):
    def __init__(self, path, debug=False):
        self.bundle_path = os.path.abspath(path)
        self.supported_files = [
            'bundle.yaml', 'bundle.json',    # v4
            'bundles.yaml', 'bundles.json',  # v3
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
        v4_keys = {'services', 'relations', 'machines', 'series'}
        bundle_keys = set(data.keys())
        return bool(v4_keys & bundle_keys)

    def bundle_file(self, parse=True):
        for f in self.supported_files:
            if os.path.isfile(os.path.join(self.bundle_path, f)):
                with open(os.path.join(self.bundle_path, f)) as d:
                    return yaml.safe_load(d.read()) if parse else d.read()

        raise Exception('No bundle.json or bundle.yaml file found')

    def proof(self, remote=True, server=None, port=None, secure=True):
        lint = BundleLinter(self.debug)
        lint.local_proof(self)
        if remote:
            lint.remote_proof(self, server, port, secure)
        else:
            lint.info('No remote checks performed')

        return lint.lint, lint.exit_code

    def promulgate(self):
        pass
