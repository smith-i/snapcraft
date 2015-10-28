# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import snapcraft
import urllib.request
import os.path
from subprocess import check_call, check_output, CalledProcessError
import json
from pprint import pprint


class AWSIoTPlugin(snapcraft.BasePlugin):

    @classmethod
    def schema(cls):
        return {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'properties': {
                # True if new keys should be generated by Amazon,
                # otherwise generate keys locally
                'generatekeys': {
                    'type': 'boolean',
                    'default': True
                },
                # Which policy document should be used. Optional.
                # Allow all IoT will be used if not specified
                'policydocument': {
                    'type': 'string',
                    'default': ''
                },
                # Which policy name should be used. Optional.
                # 'PubSubToAnyTopic' will be used if not specified
                'policyname': {
                    'type': 'string',
                    'default': 'PubSubToAnyTopic'
                },
                # The thing to create
                'thing': {
                    'type': 'string',
                },
                # AWS Endpoint to use if non-default
                'endpoint': {
                    'type': 'string',
                },
            },
            'required': ['thing']
        }

    def __init__(self, name, options):
        super().__init__(name, options)
        self.aws = ['python3',
                    os.path.join(self.stagedir, 'usr', 'bin', 'aws'),
                    'iot']

        if (options.endpoint):
            self.aws.extend(['--endpoint', options.endpoint])

    def pull(self):
        return True

    def run_to_file(self, cmds, filename):
        output = self.run_output(cmds, cwd=self.builddir)
        with open(filename, 'w') as f:
            f.write(output)

    def build(self):
        certsdir = os.path.join(self.builddir, 'certs')
        # Make the certs directory if it does not exist
        os.makedirs(certsdir, exist_ok=True)

        # What should we do with certificates?
        if self.options.generatekeys:
            # generate new keys
            self.run_to_file(self.aws + ['create-keys-and-certificate',
                                         '--set-as-active'],
                             os.path.join(certsdir, 'certs.json'))
            # separate into different files
            with open(os.path.join(certsdir, 'certs.json')) as data_file:
                self.data = json.load(data_file)

            with open(os.path.join(certsdir, 'cert.pem'), 'w') as text_file:
                text_file.write(self.data['certificatePem'])
            with open(os.path.join(certsdir, 'privateKey.pem'), 'w') \
                    as text_file:
                text_file.write(self.data['keyPair']['PrivateKey'])
            with open(os.path.join(certsdir, 'publicKey.pem'), 'w') \
                    as text_file:
                text_file.write(self.data['keyPair']['PublicKey'])
        else:
            # generate private key
            csr = os.path.join(certsdir, 'cert.csr')
            if not self.run(['openssl', 'genrsa',
                             '-out', os.path.join(certdir, 'privateKey.pem'),
                             '2048']) or not \
                    self.run(['openssl', 'req', '-new',
                              '-key', os.path.join(certdir, 'privateKey.pem'),
                              '-out', csr]):
                return False

            # generate new keys based on a csr
            # TODO: test the rest of the methods because it always gives
            # an invalid CSR request
            certresp = os.path.join(self.builddir, 'certresponse.txt')
            self.run_to_file(self.aws + ['create-certificate-from-csr',
                                         '--certificate-signing-request', csr,
                                         '--set-as-active'],
                             certresp)
            with open(certresp) as data_file:
                self.data = json.load(data_file)

            self.run_to_file(self.aws + ['describe-certificate',
                                         '--certificate-id',
                                         self.data['arn'].split(':cert/')[1],
                                         '--output',
                                         'text',
                                         '--query',
                                         '{}Description.{}Pem'.format(
                                            'certificate')
                                         ],
                             os.path.join(certdir, 'cert.pem'))

        # Extra check, but good to ensure
        if self.data is None:
            return False

        # Get the root certificate
        self.filename = urllib.request.urlretrieve(
            'https://www.symantec.com/content/en/us/enterprise/verisign/roots/'
            'VeriSign-Class%203-Public-Primary-Certification-Authority-G5.pem',
            filename=os.path.join(certsdir, 'rootCA.pem'))

        # attach policy to certificate
        if self.options.policydocument is not '':
            self.pd = ('{\n'
                       '     "Version": "2012-10-17",\n'
                       '     "Statement": [{\n'
                       '     "Effect":	"Allow",\n'
                       '       "Action":["iot:*"],\n'
                       '       "Resource": ["*"]\n'
                       '     }]\n'
                       '}\n'
                       )
            self.options.policydocument = "policydocument"
            with open(self.options.policydocument, "w") as text_file:
                text_file.write(self.pd)

        arnresp = os.path.join(self.builddir, 'arnresponse.txt')
        if not self.run_to_file(self.aws + ['create-policy',
                                            '--policy-name',
                                            self.options.policyname,
                                            '--policy-document',
                                            'file://' +
                                            self.options.policydocument],
                                arnresp):
            print("If the policy name already exists ' \
                  'then creating it will fail. You can ignore this error.")
            if not self.run_to_file(self.aws + ['get-policy',
                                                '--policy-name',
                                                self.options.policyname],
                                    arnresp):
                return False

        with open('arnresponse.txt') as data_file:
                self.data = json.load(data_file)

        if not self.run(self.aws + ['attach-principal-policy',
                                    '-‐principal-arn',
                                    self.data["policyArn"],
                                    '--policy-name',
                                    self.options.policyname]):
            return False

        if not self.run(self.aws + ['create-thing',
                                    '--thing-name',
                                    self.options.thing]):
            return False

        print("Created Thing: %s" % self.options.thing)
        return True

    def run(self, cmd, **kwargs):
        return True

    def stage_fileset(self):
        fileset = super().stage_fileset()
        fileset.append('-certresponse.txt')
        fileset.append('-arnresponse.txt')
        return fileset
