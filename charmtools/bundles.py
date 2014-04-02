import glob
import json
import os
import re
import yaml

from linter import Linter
from charmworldlib import bundle as cw_bundle


charm_url_includes_id = re.compile(r'-\d+$').search


class BundleLinter(Linter):
    def validate(self, contents):
        """Validate the bundle.

        Tests:
          * name not 'envExport' (generic name for exports by Juju GUI),
          * No series set and not inheriting,
          * Position annotations give for each service.
        """
        for name, bdata in contents.items():
            if name == 'envExport':
                self.warn('envExport is the default export name. Please '
                          'use a unique name')

            if 'series' not in bdata and 'inherits' not in bdata:
                self.info("%s: No series defined" % name)

            if 'services' in bdata:
                for svc, sdata in bdata['services'].items():
                    if 'annotations' not in sdata:
                        self.warn('%s: %s: No annotations found, will render '
                                  'poorly in GUI' % (name, svc))
                    if not charm_url_includes_id(sdata['charm']):
                        self.warn(
                            '%s: charm URL should include a revision' % svc)

            else:
                if 'inherits' not in bdata:
                    self.err("%s: No services defined" % name)
                    return

    def local_proof(self, bundle):
        try:
            data = bundle.bundle_file()
        except:
            raise

        readmes = glob.glob(os.path.join(bundle.bundle_path, 'README*'))
        if len(readmes) < 1:
            self.warn('No readme file found')

        self.validate(data)

    def remote_proof(self, bundle, server, port, secure):
        if server is not None or port is not None:
            # Use the user-specified overrides for the remote server.
            bundles = cw_bundle.Bundles(server=server, port=port,
                                        secure=secure)
        else:
            # Otherwise use the defaults.
            bundles = cw_bundle.Bundles()

        deployer_file = bundle.bundle_file(parse=True)
        proof_output = bundles.proof(deployer_file)

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
        self.supported_files = ['bundles.yaml', 'bundles.json']
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
