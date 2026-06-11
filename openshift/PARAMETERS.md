# OpenShift Template Parameters

This document lists all the parameters you need to provide when deploying Copr to OpenShift using the plain templates.

## Overview

The templates have been converted from Jinja2 to plain OpenShift manifests. Configuration files and secrets need to be base64-encoded before applying them.

## Required Parameters

### Project Configuration

- `PROJECT_NAME` - Name of the OpenShift project (namespace)

### PostgreSQL

- `POSTGRES_USER_B64` - PostgreSQL username (base64-encoded)
- `POSTGRES_PASSWORD_B64` - PostgreSQL password (base64-encoded)
- `POSTGRES_DATABASE_NAME_B64` - PostgreSQL database name (base64-encoded)
- `POSTGRES_STORAGE_SIZE` - Storage size for PostgreSQL (e.g., "1Gi" for dev, "12Gi" for prod)
- `POSTGRESQL_IMAGE` - PostgreSQL container image (can be left empty to use ImageStream)

### Redis

- `REDIS_IMAGE` - Redis container image (can be left empty to use ImageStream)

### Frontend

- `FRONTEND_CONFIG_B64` - Frontend configuration file content (base64-encoded)
  - Source: `config/frontend-copr.conf` (fill in your values)
- `COPR_FRONTEND_IMAGE` - Frontend container image (can be left empty to use ImageStream)

### Backend

- `BACKEND_CONFIG_B64` - Backend configuration file content (base64-encoded)
  - Source: `config/backend-copr-be.conf` (fill in your values)
- `BACKEND_HTTPD_CONFIG_B64` - Backend nginx configuration (base64-encoded)
  - Source: `config/backend-nginx.conf`
- `COPR_BACKEND_IMAGE` - Backend container image (can be left empty to use ImageStream)
- `NGINX_IMAGE` - Nginx container image (can be left empty to use ImageStream)
- `AWS_SSH_PRIVATE_KEY_B64` - AWS SSH private key for builders (base64-encoded)

### DistGit

- `DISTGIT_CONFIG_B64` - DistGit configuration (base64-encoded)
  - Source: `config/distgit-distgit.conf`
- `DISTGIT_COPR_CONFIG_B64` - DistGit Copr configuration (base64-encoded)
  - Source: `config/distgit-copr.conf.example` (fill in your values)
- `COPR_DISTGIT_IMAGE` - DistGit container image (can be left empty to use ImageStream)

### Resalloc

- `RESALLOC_POOL_YAML_B64` - Resalloc pool configuration (base64-encoded)
  - Source: `config/resalloc-pool.yaml.example` (fill in your values)
- `RESALLOC_SERVER_YAML_B64` - Resalloc server configuration (base64-encoded)
  - Source: `config/resalloc-server.yaml`
- `RESALLOC_SPINUP_PLAYBOOK_B64` - Resalloc spinup playbook (base64-encoded)
  - Source: `config/resalloc-spinup-playbook.yml.example` (fill in your values)
- `AWS_CREDENTIALS_B64` - AWS credentials file (base64-encoded)
  - Source: `config/resalloc-aws-credentials.example` (fill in your values)
- `RESALLOC_IMAGE` - Resalloc container image (can be left empty to use ImageStream)

### Keygen

- `COPR_KEYGEN_IMAGE` - Keygen container image (can be left empty to use ImageStream)

## How to Base64 Encode Files

To encode a configuration file to base64:

```bash
# Linux/Mac
cat config/your-file.conf | base64 -w 0

# Or to save to a file
base64 -w 0 < config/your-file.conf > config/your-file.conf.b64
```

## Deployment Methods

### Method 1: Using `oc process` with a parameter file

Create a `params.env` file:
```
PROJECT_NAME=my-copr
POSTGRES_USER_B64=$(echo -n "copr-fe" | base64)
POSTGRES_PASSWORD_B64=$(echo -n "your-password" | base64)
...
```

Then apply:
```bash
oc process -f services/postgres.yml --param-file=params.env | oc apply -f -
```

### Method 2: Using `envsubst`

Export environment variables and use `envsubst`:
```bash
export PROJECT_NAME=my-copr
export POSTGRES_USER_B64=$(echo -n "copr-fe" | base64)
...
envsubst < services/postgres.yml | oc apply -f -
```

### Method 3: Manual substitution

For simple deployments, you can manually edit the YAML files and replace `${PARAMETER}` with actual values before applying.

## Image Parameters

For most image parameters (e.g., `COPR_FRONTEND_IMAGE`, `POSTGRESQL_IMAGE`), you can:

1. Leave them empty (`""` or `" "`) to let OpenShift use the image from the ImageStream triggers
2. Or provide a specific image reference if you want to override the ImageStream

The original Ansible playbook detected current images to avoid unnecessary redeployments. With plain templates, it's simpler to let ImageStream triggers handle updates automatically.
