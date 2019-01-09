# Vaultk8

This is an update to previous method... perfect case scenario is to use this in an init contianer. This will generate secrets.conf file that will be stored in a location of your choosing. Expose these secrets to your container.


Currently supports following:
- Vault:
    1. Secrets Backend KV
- k8:
    1. Authentication against k8 backend
    2. Generates secrets in key='value' format so they can be safely sourced for environment variables before launching app.

Future:
- LOTS of code cleanup required... this is quick rough start

Python Version Support : 3.7.2

## Usage

The help page provides information on proper parameters to pass
```sh                                                 
Generates kubernetes secrets by pulling secrets from vault and generating k8
configs

positional arguments:
  {kv}                  sub-command help
    kv                  Pulls secrets from KV backend

optional arguments:
  -h, --help            show this help message and exit
  --verbose, -v         Log verbosity (default: None)
  --no-tls-verify       Disable tls verification (default: True)
  --vault-address VAULT_ADDRESS
                        Enable tls verification (default:
                        http://127.0.0.1:8200)
  --generated-conf GENERATED_CONF, -g GENERATED_CONF
                        Directory where the new generated secrets will be
                        stored (stored as secrets.conf) (default: None)
  --k8-role K8_ROLE     Role to validate against vault K8 backend (default:
                        None)
  --k8-auth-mount-point K8_AUTH_MOUNT_POINT
                        Mount point for k8 auth (default: kubernetes)
```

Once the program finished it writes out **secrets.conf** to the folder specified by **generated-conf**:

This program should be used in init container specifically to source secrets before launching app. Steps for ideal scenario:
1. generate secrets in init container
2. safe secrets to a shared mount
3. App loads in normal lifecycle and sources secrets (environmnent variables)

Currently, app only supports pulling secrets from KV (v2) backend. Sample of how to run program

```sh
python3 app/vaultk8.py --vault-address https:/vault.test.com --g /muvaki --k8-role qa-app --k8-auth-mount-point qa kv qa/app
```

**note**: if you are going to run it with docker, you will have to mount your local diretory where the k8.yaml config is sitting in order for the configs to be readable. In example above, /muvaki would be volume mounted.