import os
import yaml
import glob
import json

from linter import Linter
from charmworldlib import bundle as cw_bundle


class BundleLinter(Linter):
    def validate(self, contents):
        for name, bdata in contents.items():
            if name == 'envExport':
                self.warn('envExport is the default export name. Please '
                          'use a unique name')

            if 'series' not in bdata and 'inherits' not in bdata:
                self.info("%s: No series defined" % name)

            if 'services' in bdata:
                for svc, sdata in bdata['services'].items():
                    if not 'annotations' in sdata:
                        self.warn('%s: %s: No annotations found, will render '
                                  'bad in GUI' % (name, svc))
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

    def remote_proof(self, bundle):
        bundles = cw_bundle.Bundles()
        deployer_file = bundle.bundle_file(parse=True)
        proof_output = bundles.proof(deployer_file)

        # Loop through errors for verbose outputing.
        # http://paste.mitechie.com/show/1048/
        if self.debug:
            print json.dumps(proof_output, 2)

        if 'error_messages' in proof_output:
            for message in proof_output['error_messages']:
                self.err(message)


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

    def proof(self, remote=True):
        lint = BundleLinter(self.debug)
        lint.local_proof(self)
        if remote:
            lint.remote_proof(self)
        else:
            lint.info('No remote checks performed')

        return lint.lint, lint.exit_code

    def promulgate(self):
        pass
