# Vaultk8

Intention of **vaultk8** is to be used as an init container to authenticate and write secrets for apps to consume in kubernetes. This app generates secret config file that will be stored in a location of your choosing.


Currently supports following:
- Secrets backend:
    1. Supports KV v2 secrets backend
- Authentication:
    1. Kubernetes Authentication backend
- Output:
  1. Toml: The path given in KV is traversed to generate a TOML formatted secrets file with 'section names' being the root of each of the paths
  2. env: 'key=value' file generated
  3. export: 'export key=value' file generated

Python Version Support : 3.7.2

## Usage

The help page provides information on proper parameters to pass
```sh                                                 
Generates secrets by pulling them from vault. Uses kubernetes SA to
authenticate against backend

positional arguments:
  {kv}                  sub-command help
    kv                  Pulls secrets from KV backend

optional arguments:
  -h, --help            show this help message and exit
  --verbose, -v         Log verbosity (default: 0)
  --no-tls-verify       Disable tls verification (default: True)
  --vault-address VAULT_ADDRESS
                        Enable tls verification (default:
                        http://127.0.0.1:8200)
  --generated-conf-dir GENERATED_CONF_DIR, -g GENERATED_CONF_DIR
                        Full path where the new generated secrets will be
                        stored (default: None)
  --generated-conf-filename GENERATED_CONF_FILENAME, -n GENERATED_CONF_FILENAME
                        Name of the secrets file to generate (default:
                        secrets.conf)
  --k8-role K8_ROLE     Role to validate against vault K8 backend (default:
                        None)
  --k8-auth-mount-point K8_AUTH_MOUNT_POINT
                        Mount point for k8 auth (default: kubernetes)
```

kv options are as follows
```sh
Pulls secrets from KV backend

positional arguments:
  secrets_path          Secrets Path in KV backend to pull all the secrets
                        from

optional arguments:
  -h, --help            show this help message and exit
  --kv-mount-point KV_MOUNT_POINT, -m KV_MOUNT_POINT
                        Backend KV mountpoint (default: kv)
  --format {export,env,toml}
                        Set config with export followed by key=value (default:
                        env)
```

This program should be used in init container specifically to source secrets before launching app. Steps for ideal scenario:
1. Create Kubernetes Service account as described in [vault kubernetes auth backend documentation](https://www.vaultproject.io/docs/auth/kubernetes.html)

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vault
---
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRoleBinding
metadata:
  name: role-tokenreview-binding
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:auth-delegator
subjects:
- kind: ServiceAccount
  name: vault
  namespace: default
```

2. Create a kubernetes auth backend and attach roles with appropriate policies. For example, staging cluster should hit backend that only allow staging cluster with appropriate secret access.
3. generate secrets in init container once backend have been configured
```yaml
# sample init-container config for kubernetes
# note this is not the full deployment spec
...
spec:
  serviceAccountName: vault
  initContainers:
    - name: vaultk8
      image: muvaki/vaultk8
      args:
        - "--vault-address"
        - "https://vault.com"
        - "-g"
        - "/etc/vault"
        - "-n"
        - "env"
        - "--k8-role"
        - "vault"
        - "--k8-auth-mount-point"
        - "kubernetes"
        - "kv"
        - "staging/my_app"
...
```
4. save secrets to a shared volume mount so your apps can consume it. Make it memory to be volatile and not persistant
```yaml
# sample kubernetes deployment spec
volumes:
        - name: secrets-vol
          emptyDir:
            medium: "Memory"
```
5. App loads in normal lifecycle and sources secrets (environmnent variables)
```yaml
     containers:
      - name: muvaki
        image: muvaki-web
        command:
          - "bash"
          - "-c"
          - ". /etc/vault/env && node hello.js"
```