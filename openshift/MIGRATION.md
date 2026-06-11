# Migration from Jinja2 Templates to Plain OpenShift Templates

## What Changed

The OpenShift deployment has been converted from Ansible + Jinja2 templates to plain OpenShift YAML templates with parameter substitution.

### Old Approach (Jinja2/Ansible)
- Used `deploy.yml` Ansible playbook
- Jinja2 templates in `services/*.yml.j2` and `config/*.j2`
- Variables defined in `secret-vars.yml`
- Ansible handled image detection and secret generation

### New Approach (Plain OpenShift)
- Direct deployment with `oc` or `envsubst`
- Plain YAML templates in `services/*.yml`
- Parameters in environment variables or `params.env`
- Manual configuration preparation required

## File Mapping

### Templates Converted

| Old File (Jinja2) | New File (Plain YAML) |
|-------------------|----------------------|
| `project.yaml.j2` | `project.yaml` |
| `services/backend.yml.j2` | `services/backend.yml` |
| `services/frontend.yml.j2` | `services/frontend.yml` |
| `services/postgres.yml.j2` | `services/postgres.yml` |
| `services/redis.yml.j2` | `services/redis.yml` |
| `services/distgit.yml.j2` | `services/distgit.yml` |
| `services/resalloc.yml.j2` | `services/resalloc.yml` |
| `services/keygen.yml.j2` | `services/keygen.yml` |

### Config Files

| Old File (Jinja2) | New File (Example) |
|-------------------|-------------------|
| `config/distgit-copr.conf.j2` | `config/distgit-copr.conf.example` |
| `config/resalloc-aws-credentials.j2` | `config/resalloc-aws-credentials.example` |
| `config/resalloc-pool.yaml.j2` | `config/resalloc-pool.yaml.example` |
| `config/resalloc-spinup-playbook.yml.j2` | `config/resalloc-spinup-playbook.yml.example` |

Files without variables (like `distgit-distgit.conf.j2` and `resalloc-server.yaml.j2`) were renamed to remove the `.j2` extension.

## Variable Substitution Changes

### Jinja2 Format
```yaml
image: "{{ copr_backend_image }}"
data:
  config: "{{ backend_config | b64encode }}"
```

### OpenShift Parameter Format
```yaml
image: ${COPR_BACKEND_IMAGE}
data:
  config: ${BACKEND_CONFIG_B64}
```

**Important:** Base64 encoding is no longer automatic - you must encode configuration files before deployment.

## Migration Steps

If you have an existing deployment using the Ansible approach:

1. **Export your current configuration:**
   - Save your `secret-vars.yml` file
   - Note all configuration values

2. **Prepare new config files:**
   ```bash
   cd openshift/config/
   cp distgit-copr.conf.example distgit-copr.conf
   cp resalloc-pool.yaml.example resalloc-pool.yaml
   cp resalloc-aws-credentials.example resalloc-aws-credentials
   cp resalloc-spinup-playbook.yml.example resalloc-spinup-playbook.yml
   # Edit each file with your values from secret-vars.yml
   ```

3. **Use the preparation script:**
   ```bash
   ./prepare-deployment.sh
   ```

4. **Deploy with new templates:**
   ```bash
   source params.env
   envsubst < project.yaml | oc apply -f -
   for svc in postgres redis frontend backend distgit resalloc keygen; do
     envsubst < services/${svc}.yml | oc apply -f -
   done
   ```

## Mapping secret-vars.yml to Parameters

| secret-vars.yml | New Parameter | Notes |
|----------------|---------------|-------|
| `project` | `PROJECT_NAME` | Project/namespace name |
| `postgres_user` | `POSTGRES_USER_B64` | Base64-encoded |
| `postgres_password` | `POSTGRES_PASSWORD_B64` | Base64-encoded |
| `postgres_database_name` | `POSTGRES_DATABASE_NAME_B64` | Base64-encoded |
| `deployment` (prod/dev) | `POSTGRES_STORAGE_SIZE` | "12Gi" for prod, "1Gi" for dev |
| `frontend_backend_password` | In `FRONTEND_CONFIG_B64` | Part of config file content |
| `frontend_base_url` | In config files | Multiple places |
| `distgit_fqdn` | In config files | Multiple places |
| `backend_fqdn` | In config files | Multiple places |
| `aws_config.access_key_id` | In `AWS_CREDENTIALS_B64` | Part of credentials file |
| `aws_config.secret_access_key` | In `AWS_CREDENTIALS_B64` | Part of credentials file |
| `aws_config.ssh_key.private` | `AWS_SSH_PRIVATE_KEY_B64` | Base64-encoded |
| `aws_config.ssh_key.public` | In config files | In spinup playbook |
| `aws_config.ssh_key.name` | In config files | In pool config |

## Benefits of the New Approach

1. **No Ansible dependency** - Deploy from any system with `oc` or `kubectl`
2. **Simpler automation** - Easier to integrate with CI/CD pipelines
3. **More portable** - Works with any Kubernetes/OpenShift tooling
4. **GitOps friendly** - Plain YAML is easier to version control and review

## Drawbacks to Consider

1. **Manual preparation** - No automatic base64 encoding or image detection
2. **More verbose** - Need to manage parameters file
3. **Less validation** - Ansible provided some configuration validation

## Backwards Compatibility

The old `deploy.yml` playbook and `.j2` templates are still present but deprecated. They will be removed in a future release. Please migrate to the new plain templates.

## Getting Help

- See `README-NEW.md` for deployment instructions
- See `PARAMETERS.md` for complete parameter reference
- Use `prepare-deployment.sh` to simplify configuration preparation
