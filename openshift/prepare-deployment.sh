#!/bin/bash
# Helper script to prepare Copr OpenShift deployment
# This script helps you encode configuration files and generate a params.env file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"
TMP_DIR="${TMP_DIR:-/tmp/copr-openshift-deploy}"

mkdir -p "$TMP_DIR"

echo "=== Copr OpenShift Deployment Preparation ==="
echo

# Check required config files exist
check_config_file() {
    if [ ! -f "$1" ]; then
        echo "ERROR: Required config file not found: $1"
        echo "Please create it from the .example file if available"
        exit 1
    fi
}

echo "Step 1: Checking configuration files..."
check_config_file "$CONFIG_DIR/frontend-copr.conf"
check_config_file "$CONFIG_DIR/backend-copr-be.conf"
check_config_file "$CONFIG_DIR/backend-nginx.conf"
check_config_file "$CONFIG_DIR/distgit-distgit.conf"
check_config_file "$CONFIG_DIR/distgit-copr.conf"
check_config_file "$CONFIG_DIR/resalloc-server.yaml"
check_config_file "$CONFIG_DIR/resalloc-pool.yaml"
check_config_file "$CONFIG_DIR/resalloc-spinup-playbook.yml"
check_config_file "$CONFIG_DIR/resalloc-aws-credentials"
echo "✓ All config files found"
echo

echo "Step 2: Base64 encoding configuration files..."
base64 -w 0 < "$CONFIG_DIR/frontend-copr.conf" > "$TMP_DIR/frontend-copr.conf.b64"
base64 -w 0 < "$CONFIG_DIR/backend-copr-be.conf" > "$TMP_DIR/backend-copr-be.conf.b64"
base64 -w 0 < "$CONFIG_DIR/backend-nginx.conf" > "$TMP_DIR/backend-nginx.conf.b64"
base64 -w 0 < "$CONFIG_DIR/distgit-distgit.conf" > "$TMP_DIR/distgit-distgit.conf.b64"
base64 -w 0 < "$CONFIG_DIR/distgit-copr.conf" > "$TMP_DIR/distgit-copr.conf.b64"
base64 -w 0 < "$CONFIG_DIR/resalloc-server.yaml" > "$TMP_DIR/resalloc-server.yaml.b64"
base64 -w 0 < "$CONFIG_DIR/resalloc-pool.yaml" > "$TMP_DIR/resalloc-pool.yaml.b64"
base64 -w 0 < "$CONFIG_DIR/resalloc-spinup-playbook.yml" > "$TMP_DIR/resalloc-spinup-playbook.yml.b64"
base64 -w 0 < "$CONFIG_DIR/resalloc-aws-credentials" > "$TMP_DIR/resalloc-aws-credentials.b64"
echo "✓ Config files encoded"
echo

echo "Step 3: Gathering deployment parameters..."
read -p "Project name (OpenShift namespace): " PROJECT_NAME
read -p "PostgreSQL username [copr-fe]: " POSTGRES_USER
POSTGRES_USER="${POSTGRES_USER:-copr-fe}"
read -sp "PostgreSQL password: " POSTGRES_PASSWORD
echo
read -p "PostgreSQL database name [copr-db]: " POSTGRES_DB
POSTGRES_DB="${POSTGRES_DB:-copr-db}"
read -p "PostgreSQL storage size (e.g., 1Gi for dev, 12Gi for prod) [1Gi]: " POSTGRES_STORAGE
POSTGRES_STORAGE="${POSTGRES_STORAGE:-1Gi}"
read -p "Path to AWS SSH private key: " AWS_KEY_PATH

if [ ! -f "$AWS_KEY_PATH" ]; then
    echo "ERROR: AWS SSH key not found at $AWS_KEY_PATH"
    exit 1
fi

echo
echo "Step 4: Encoding credentials..."
echo -n "$POSTGRES_USER" | base64 > "$TMP_DIR/postgres-user.b64"
echo -n "$POSTGRES_PASSWORD" | base64 > "$TMP_DIR/postgres-password.b64"
echo -n "$POSTGRES_DB" | base64 > "$TMP_DIR/postgres-db.b64"
base64 -w 0 < "$AWS_KEY_PATH" > "$TMP_DIR/aws-ssh-key.b64"
echo "✓ Credentials encoded"
echo

echo "Step 5: Generating params.env file..."
cat > "$TMP_DIR/params.env" <<EOF
PROJECT_NAME=$PROJECT_NAME
POSTGRES_USER_B64=$(cat "$TMP_DIR/postgres-user.b64")
POSTGRES_PASSWORD_B64=$(cat "$TMP_DIR/postgres-password.b64")
POSTGRES_DATABASE_NAME_B64=$(cat "$TMP_DIR/postgres-db.b64")
POSTGRES_STORAGE_SIZE=$POSTGRES_STORAGE
POSTGRESQL_IMAGE=
REDIS_IMAGE=
FRONTEND_CONFIG_B64=$(cat "$TMP_DIR/frontend-copr.conf.b64")
COPR_FRONTEND_IMAGE=
BACKEND_CONFIG_B64=$(cat "$TMP_DIR/backend-copr-be.conf.b64")
BACKEND_HTTPD_CONFIG_B64=$(cat "$TMP_DIR/backend-nginx.conf.b64")
COPR_BACKEND_IMAGE=
NGINX_IMAGE=
AWS_SSH_PRIVATE_KEY_B64=$(cat "$TMP_DIR/aws-ssh-key.b64")
DISTGIT_CONFIG_B64=$(cat "$TMP_DIR/distgit-distgit.conf.b64")
DISTGIT_COPR_CONFIG_B64=$(cat "$TMP_DIR/distgit-copr.conf.b64")
COPR_DISTGIT_IMAGE=
RESALLOC_POOL_YAML_B64=$(cat "$TMP_DIR/resalloc-pool.yaml.b64")
RESALLOC_SERVER_YAML_B64=$(cat "$TMP_DIR/resalloc-server.yaml.b64")
RESALLOC_SPINUP_PLAYBOOK_B64=$(cat "$TMP_DIR/resalloc-spinup-playbook.yml.b64")
AWS_CREDENTIALS_B64=$(cat "$TMP_DIR/resalloc-aws-credentials.b64")
RESALLOC_IMAGE=
COPR_KEYGEN_IMAGE=
EOF

cp "$TMP_DIR/params.env" "$SCRIPT_DIR/params.env"
echo "✓ Parameters file created: $SCRIPT_DIR/params.env"
echo

echo "=== Preparation Complete ==="
echo
echo "Next steps:"
echo "1. Review the generated params.env file"
echo "2. Source it before deployment:"
echo "   source $SCRIPT_DIR/params.env"
echo "3. Deploy the project:"
echo "   envsubst < project.yaml | oc apply -f -"
echo "4. Deploy services:"
echo "   for svc in postgres redis frontend backend distgit resalloc keygen; do"
echo "     envsubst < services/\${svc}.yml | oc apply -f -"
echo "   done"
echo
echo "Or use the deploy.sh script if available."
