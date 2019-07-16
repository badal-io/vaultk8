#!/usr/bin/env python

"""
vaultk8 generates secret files from paths in KV. Supports 3 formats:
- key=value
- export key=value
- TOML: builds of the headings in the root of KV store
"""

import os
import sys
import hvac
import yaml
import toml
import argparse
import logging

log = logging.getLogger('vaultk8')

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
        default=0,
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
        '--generated-conf-dir',
        '-g',
        required=True,
        action=readable_dir,
        help='Full path where the new generated secrets will be stored')
    parser.add_argument(
        '--generated-conf-filename',
        '-n',
        type=str,
        default='secrets.conf',
        help='Name of the secrets file to generate')
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
        '--format',
        type=str,
        choices=['export', 'env', 'toml'],
        help='Set config with export followed by key=value',
        default='env')
    kv_parser.set_defaults(func=kv)
    kv_parser.add_argument(
        'secrets_path',
        type=str,
        help='Secrets Path in KV backend to pull all the secrets from'
    )
    
    arguments = parser.parse_args()

    # set log level
    log.setLevel(max(3 - arguments.verbose, 1) * 10)
    return arguments

def Merge(dict1, dict2): 
    res = {**dict1, **dict2} 
    return res 

def vaultAuth(vault_address, tls, mount_point, role):
    log.info("Authenticating via K8 backend")
    client = hvac.Client(url=vault_address) if tls \
        else hvac.Client(url=vault_address, verify=False)

    f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
    jwt = f.read()
    result = client.auth_kubernetes(role, jwt.strip(), mount_point=mount_point)
    client.token = result['auth']['client_token']

    assert client.is_authenticated()

    return client

def writeEnvConfig(filename, data, file_format):
    log.info("writing secrets to " + filename)
    # Generates the secrets in key=value or toml
    fh = open(filename, "w")
    if file_format == 'toml':
        fh.write(toml.dumps(data))
    else:
        for k, v in data.items():
            if file_format == 'export':
                fh.write('export ' + k.strip()+'='+'\''+v.strip()+'\'\n')
            else:
                fh.write(k.strip()+'='+'\''+v.strip()+'\'\n')
    fh.close()

def readKVSecrets(client, secrets_path, mount_point, value_type='secrets'):
    secret = {}
    try:
        if value_type == 'secrets':
            secret = client.secrets.kv.v2.read_secret_version(path=secrets_path, mount_point=mount_point)['data']['data']
        else:
            secret = client.secrets.kv.v2.list_secrets(path=secrets_path, mount_point=mount_point)['data']
    except None:
        pass
    finally:
        return secret

def getTOMLFormat(client, path, mount):
    tmp_toml = {}
    # Reads any keys stored in root of path and adds it to the toml dict
    toml = readKVSecrets(client, path, mount)

    # recursively traverses the tree to generate keys and get secrets for kv backend
    # selection names are considered the root of the path in KV with key/value inside.
    # any key/value that fall under the path are added under the subsequent selection name.
    kv_keys = readKVSecrets(client, path, mount, 'key')
    if 'keys' in kv_keys:
        for k in kv_keys['keys']:
            if k.endswith('/'):
                # this is to prevent same keys being traversed twice
                if k[:-1] in kv_keys['keys']:
                    continue
                else:
                    tmp_toml[k[:-1]] = getTOMLFormat(client, path + '/' + k[:-1], mount)
            else:
                tmp_toml[k] = getTOMLFormat(client, path + '/' + k, mount)
        toml = Merge(tmp_toml, toml)
    return toml

def kv(args):
    results = {}
    log.info("grabbing secrets from KV")
    # authenticating against vault
    client =  vaultAuth(args.vault_address, args.no_tls_verify, args.k8_auth_mount_point, role=args.k8_role)
    # setting default kv configuration
    if args.format == 'toml':
        log.info("generating TOML formatted secrets")
        results = getTOMLFormat(client, args.secrets_path, args.kv_mount_point)
    else:
        log.info("generating K/V formatted secrets")
        results = readKVSecrets(client, args.secrets_path, args.kv_mount_point)

    # write out the secrets
    filename = args.generated_conf_dir + '/' + args.generated_conf_filename
    writeEnvConfig(filename, results, args.format)

def main():
    """ Entry point """
    # sets up debug logging and logger format
    logging.basicConfig(format='%(name)s (%(levelname)s): %(message)s')
    # parsing arguments
    try:
        args = _parse_argument()
        args.func(args)
    except Exception as e:
        log.error('Caught an unexpected exception: {}'.format(e))
    finally:
        logging.shutdown()

if __name__ == '__main__':
    sys.exit(main())