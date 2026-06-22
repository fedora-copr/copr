# Deploy Copr build system in OpenShift

This directory contains OpenShift templates for deploying a fully-working Copr build system infrastructure into an OpenShift cluster, with builders (virtual machines) being automatically started/stopped in external clouds (currently just pre-configured AWS).

**Note:** At the time of writing this document, it is not common to be able to start privileged containers in OpenShift, nor rootless containers (user namespaces). Therefore, builders need to stay as virtual machines only.

## Quick Start

The templates have been converted from Jinja2/Ansible to plain OpenShift manifests with parameters. This simplifies deployment but requires more manual configuration preparation.

### Prerequisites

1. An OpenShift cluster and `oc` CLI access
2. AWS credentials for EC2 builder instances
3. Configuration files prepared (see below)

### Deployment Steps

#### 1. Prepare Configuration Files

Copy the example config files and fill in your values:

```bash
cd openshift/config/

# Copy and edit these files with your actual values:
cp distgit-copr.conf.example distgit-copr.conf
cp resalloc-pool.yaml.example resalloc-pool.yaml
cp resalloc-aws-credentials.example resalloc-aws-credentials
cp resalloc-spinup-playbook.yml.example resalloc-spinup-playbook.yml

# Edit the existing config files:
# - backend-copr-be.conf
# - frontend-copr.conf
```

See `PARAMETERS.md` for a complete list of required configuration values.

#### 2. Base64 Encode Configuration Files

```bash
# Encode all config files
base64 -w 0 < config/frontend-copr.conf > config/frontend-copr.conf.b64
base64 -w 0 < config/backend-copr-be.conf > config/backend-copr-be.conf.b64
base64 -w 0 < config/backend-nginx.conf > config/backend-nginx.conf.b64
base64 -w 0 < config/distgit-distgit.conf > config/distgit-distgit.conf.b64
base64 -w 0 < config/distgit-copr.conf > config/distgit-copr.conf.b64
base64 -w 0 < config/resalloc-pool.yaml > config/resalloc-pool.yaml.b64
base64 -w 0 < config/resalloc-server.yaml > config/resalloc-server.yaml.b64
base64 -w 0 < config/resalloc-spinup-playbook.yml > config/resalloc-spinup-playbook.yml.b64
base64 -w 0 < config/resalloc-aws-credentials > config/resalloc-aws-credentials.b64

# Encode PostgreSQL credentials
echo -n "copr-fe" | base64 > /tmp/postgres-user.b64
echo -n "your-postgres-password" | base64 > /tmp/postgres-password.b64
echo -n "copr-db" | base64 > /tmp/postgres-db.b64

# Encode AWS SSH key (use your actual private key file)
base64 -w 0 < ~/.ssh/your-aws-key.pem > /tmp/aws-ssh-key.b64
```

#### 3. Create Parameters File

Create a `params.env` file with all your parameters:

```bash
PROJECT_NAME=my-copr-project
POSTGRES_USER_B64=$(cat /tmp/postgres-user.b64)
POSTGRES_PASSWORD_B64=$(cat /tmp/postgres-password.b64)
POSTGRES_DATABASE_NAME_B64=$(cat /tmp/postgres-db.b64)
POSTGRES_STORAGE_SIZE=1Gi
POSTGRESQL_IMAGE=
REDIS_IMAGE=
FRONTEND_CONFIG_B64=$(cat config/frontend-copr.conf.b64)
COPR_FRONTEND_IMAGE=
BACKEND_CONFIG_B64=$(cat config/backend-copr-be.conf.b64)
BACKEND_HTTPD_CONFIG_B64=$(cat config/backend-nginx.conf.b64)
COPR_BACKEND_IMAGE=
NGINX_IMAGE=
AWS_SSH_PRIVATE_KEY_B64=$(cat /tmp/aws-ssh-key.b64)
DISTGIT_CONFIG_B64=$(cat config/distgit-distgit.conf.b64)
DISTGIT_COPR_CONFIG_B64=$(cat config/distgit-copr.conf.b64)
COPR_DISTGIT_IMAGE=
RESALLOC_POOL_YAML_B64=$(cat config/resalloc-pool.yaml.b64)
RESALLOC_SERVER_YAML_B64=$(cat config/resalloc-server.yaml.b64)
RESALLOC_SPINUP_PLAYBOOK_B64=$(cat config/resalloc-spinup-playbook.yml.b64)
AWS_CREDENTIALS_B64=$(cat config/resalloc-aws-credentials.b64)
RESALLOC_IMAGE=
COPR_KEYGEN_IMAGE=
```

#### 4. Deploy to OpenShift

```bash
# Create the project
envsubst < project.yaml | oc apply -f -

# Deploy each service
for service in postgres redis frontend backend distgit resalloc keygen; do
    envsubst < services/${service}.yml | oc apply -f -
done
```

Alternative using `oc process` (if templates are converted to OpenShift Template objects):

```bash
oc process -f services/postgres.yml --param-file=params.env | oc apply -f -
```

## Differences from Ansible Deployment

The previous deployment used Ansible with Jinja2 templates (`deploy.yml`). Key changes:

1. **No Ansible playbook** - Deploy directly with `oc` commands
2. **Manual parameter preparation** - You must prepare and base64-encode all config files yourself
3. **Simpler but less automated** - No automatic image detection or secret generation
4. **More portable** - Works in any OpenShift environment without Ansible dependencies

## Configuration Files

All configuration files are in the `config/` directory:

- **Backend**: `backend-copr-be.conf`, `backend-nginx.conf`
- **Frontend**: `frontend-copr.conf`
- **DistGit**: `distgit-distgit.conf`, `distgit-copr.conf`
- **Resalloc**: `resalloc-server.yaml`, `resalloc-pool.yaml`, `resalloc-spinup-playbook.yml`, `resalloc-aws-credentials`

Files with `.example` extension are templates - copy them and fill in your values.

## Images

Currently maintained images are at: https://quay.io/organization/copr

The templates reference these images:
- `quay.io/copr/frontend:test`
- `quay.io/copr/backend:test`
- `quay.io/copr/distgit:test`
- `quay.io/copr/keygen:test`
- `quay.io/copr/resalloc:test`

## WARNING

This deployment is in a pre-production state!

## TODO list

- copr-keygen pod signing process needs to be secured, currently the pod accepts sign requests from any other pod in the project because we "allow 0.0.0.0/0"

- start logging to stdout/stderr, so we can just do 'oc logs <podname> -c <container>', according to https://docs.openshift.com/container-platform/4.9/openshift_images/create-images.html. Alternatively at least implement log-rotation.

- we should merge https://github.com/openSUSE/obs-sign/pull/36 - currently patched Fedora-only

- zombie reaping - use tini

- Let's Encrypt automation

- starting the containers against a locally maintained code (from git root), currently we just use 'docker-compose'

- automate PostgreSQL initialization from a SQL dump file, for easier debugging of complicated scenarios

- setup cron jobs (automatic build removals, etc.)

- better container image tagging (currently everything in :test)

- automatic image builds (quay.io builds are broken for F35 https://bugzilla.redhat.com/show_bug.cgi?id=2025899)

- automatize the AWS SSH key creation/removal (this is the hardest part in the secret-vars.yml config file)

- separate the normal and secret vars (now everything needs to be in params.env)

## Research

- write an operator for starting builders hosted in OpenShift? But we need to wait for the state when "user namespaces" are "commonly" available

- automatic termination of orphaned resalloc instances - this happens easily when project is deleted (oc delete project <your project>)

- experiment with Terraform
