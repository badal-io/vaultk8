#!/usr/bin/env python

import os
import hvac
import base64
import yaml
import pprint
import argparse
from jinja2 import Environment, FileSystemLoader


class readable_dir(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir=values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentTypeError("readable_dir:{0} is not a valid path".format(prospective_dir))
        if os.access(prospective_dir, os.R_OK):
            setattr(namespace,self.dest,prospective_dir)
        else:
            raise argparse.ArgumentTypeError("readable_dir:{0} is not a readable dir".format(prospective_dir))

def _parse_argument():
    """ parse commandline input """
    parser = argparse.ArgumentParser(
        description='Generates secrets by pulling them from vault. Uses kubernetes SA to authenticate against backend',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--verbose',
        '-v',
        action='count',
        help='Log verbosity')
    parser.add_argument(
        '--no-tls-verify',
        action='store_false',
        help='Disable tls verification')
    parser.add_argument(
        '--vault-address',
        action='store',
        default='http://127.0.0.1:8200',
        help='Enable tls verification')
    parser.add_argument(
        '--generated-conf',
        '-g',
        required=True,
        action=readable_dir,
        help='Directory where the new generated secrets will be stored (stored as secrets.conf)')
    parser.add_argument(
        '--k8-role',
        required=True,
        action='store',
        help='Role to validate against vault K8 backend')
    parser.add_argument(
        '--k8-auth-mount-point',
        default='kubernetes',
        action='store',
        help='Mount point for k8 auth')
    subparsers = parser.add_subparsers(help='sub-command help')

    # Sub command that handles pulling secrets from KV backend
    kv_parser = subparsers.add_parser('kv',
        description='Pulls secrets from KV backend',
        help='Pulls secrets from KV backend',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    kv_parser.add_argument(
        '--kv-mount-point',
        '-m',
        default='kv',
        type=str,
        help='Backend KV mountpoint'
    )
    kv_parser.add_argument(
        'secrets_path',
        type=str,
        help='Secrets Path in KV backend to pull all the secrets from'
    )
    kv_parser.add_argument(
        '--export',
        action='store_true',
        help='Set config with export followed by key=value')
    kv_parser.set_defaults(func=kv)

    return parser.parse_args()

def vaultAuth(vault_address, tls, mount_point, role):
    client = hvac.Client(url=vault_address) if tls \
        else hvac.Client(url=vault_address, verify=False)

    f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
    jwt = f.read()
    result = client.auth_kubernetes(role, jwt.strip(), mount_point=mount_point)
    client.token = result['auth']['client_token']

    assert client.is_authenticated()

    return client

def writeEnvConfig(secret_dir, data, export_setting):
    # Generates the secrets in key=value format
    fh = open(secret_dir + "/secrets.conf", "w")
    for k, v in data.items():
        if export_setting:
            fh.write('export ' + k.strip()+'='+'\''+v.strip()+'\'\n')
        else:
            fh.write(k.strip()+'='+'\''+v.strip()+'\'\n')

def kv(args):
    # authenticating against vault
    client =  vaultAuth(args.vault_address, args.no_tls_verify, args.k8_auth_mount_point, role=args.k8_role)
    # setting default kv configuration
    secret_version_response = client.secrets.kv.v2.read_secret_version(path=args.secrets_path, mount_point=args.kv_mount_point)
    # write out the secrets
    writeEnvConfig(args.generated_conf,secret_version_response['data']['data'], args.export)

def main():
    """ Entry point """
    # parsing arguments
    args = _parse_argument()
    args.func(args)

    return 0

if __name__ == '__main__':
    try:
        exit(main())
    except Exception as e:
        print('Caught an unexpected exception: {}'.format(e))
        exit(1)
