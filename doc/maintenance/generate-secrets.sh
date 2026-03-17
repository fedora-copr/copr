#!/bin/bash
set -euo pipefail

# =============================================================
# Copr Secret Rotation — generator
#
# Generates all auto-generatable secrets for Fedora Copr.
# Secrets requiring manual web UI work are left as TODO.
# =============================================================

DATE=$(date +%Y-%m-%d)
DIR="copr-secrets-rotation-${DATE}"

if [[ -d "$DIR" ]]; then
    echo "ERROR: Directory $DIR already exists. Remove it first."
    exit 1
fi

mkdir -p "${DIR}/files/copr"

gen_pass() { pwgen -s 60 1; }
hash_pass() { openssl passwd -6 -stdin <<< "$1"; }

echo "==> Generating passwords..."

COPR_SECRET_KEY=$(gen_pass)
COPR_BACKEND_PASSWORD=$(gen_pass)
COPR_BACKEND_PASSWORD_DEV=$(gen_pass)
COPR_BACKEND_PASSWORD_STG=$(gen_pass)

MACHINE_TYPES=(frontend backend distgit keygen rpmeta)

declare -A ROOT_PLAIN ROOT_HASH
for env in prod stg; do
    for machine in "${MACHINE_TYPES[@]}"; do
        plain=$(gen_pass)
        ROOT_PLAIN["${env}_${machine}"]="$plain"
        ROOT_HASH["${env}_${machine}"]=$(hash_pass "$plain")
    done
done

echo "==> Generating SSH key pairs for buildsys (production + staging)..."
for key_env in production staging; do
    ssh-keygen -t rsa -b 4096 \
        -f "${DIR}/files/copr/buildsys.${key_env}" \
        -N "" \
        -C "copr-buildsys-${key_env}-${DATE}" \
        -q
    mv "${DIR}/files/copr/buildsys.${key_env}" "${DIR}/files/copr/buildsys.${key_env}.priv"
done

# -----------------------------------------------------------
# Root passwords plaintext reference (destroy after rotation)
# -----------------------------------------------------------
{
    echo "# Root password plaintext reference — save in Bitwarden and DESTROY after rotation"
    echo ""
    for env in prod stg; do
        echo "${env}:"
        for machine in "${MACHINE_TYPES[@]}"; do
            echo "  ${machine}: ${ROOT_PLAIN[${env}_${machine}]}"
        done
        echo ""
    done
} > "${DIR}/root-passwords-plaintext.txt"
chmod 600 "${DIR}/root-passwords-plaintext.txt"

# -----------------------------------------------------------
# Single secrets file with prod / stg sections
# -----------------------------------------------------------
cat > "${DIR}/secrets.yml" << YAML
# ============================================================
# Copr Secret Rotation — ${DATE}
#
# Merge these values into /srv/private/ansible/vars.yml
# on batcave01.


# =========================
#  SHARED (prod + stg)
# =========================

# Flask SECRET_KEY — used for CSRF and session signing.
# Rotating this invalidates all existing user sessions.
copr_secret_key: "${COPR_SECRET_KEY}"


# =========================
#  PRODUCTION
# =========================

# FE <-> BE <-> DistGit auth token (prod)
copr_backend_password: "${COPR_BACKEND_PASSWORD}"

# Root passwords — crypt(3) SHA-512 hashes
copr_root_passwords:
  prod:
YAML

for machine in "${MACHINE_TYPES[@]}"; do
    echo "    ${machine}: \"${ROOT_HASH[prod_${machine}]}\"" >> "${DIR}/secrets.yml"
done

cat >> "${DIR}/secrets.yml" << YAML


# =========================
#  STAGING / DEVEL
# =========================

# FE <-> BE <-> DistGit auth token (devel stack)
copr_backend_password_dev: "${COPR_BACKEND_PASSWORD_DEV}"
# FE <-> BE <-> DistGit auth token (staging-without-devel, currently unused)
copr_backend_password_stg: "${COPR_BACKEND_PASSWORD_STG}"

# Root passwords — crypt(3) SHA-512 hashes
copr_root_passwords:
  stg:
YAML

for machine in "${MACHINE_TYPES[@]}"; do
    echo "    ${machine}: \"${ROOT_HASH[stg_${machine}]}\"" >> "${DIR}/secrets.yml"
done

cat >> "${DIR}/secrets.yml" << YAML


# =========================
#  TODO — fill manually
# =========================

# AWS (run: aws --profile fedora-copr iam create-access-key)
copr_aws_access_key_id: "TODO"
copr_aws_secret_access_key: "TODO"

# IBM Cloud (console: Manage -> Access IAM -> API keys -> Create)
copr_cloud_ibm_token: "TODO"

# OSUOSL OpenStack (web console -> Settings -> Change Password)
# WARNING: password change takes effect immediately!
copr_openstack_osuosl_org_password: "TODO"

# Red Hat Subscription (https://access.redhat.com/management/api)
copr_red_hat_subscription_offline_token: "TODO"
copr_rhsm_activation_key: "TODO"

# Copr ping bot (log in as bot-copr-ping, regenerate API token)
# Only used on prod (skipped on devel)
copr_ping_bot_login: "TODO"
copr_ping_bot_token: "TODO"

# UptimeRobot (dashboard -> API Settings -> regenerate)
copr_uptimerobot_api_key_ro: "TODO"

# SMTP relay (coordinate with mail/infra team if rotating)
# copr_smtp_password: "TODO"
YAML

# -----------------------------------------------------------
# README
# -----------------------------------------------------------
cat > "${DIR}/README.txt" << 'EOF'
COPR SECRET ROTATION BUNDLE
============================

Structure:
  secrets.yml                       All secret vars, organized by prod/stg sections.
                                    Merge into /srv/private/ansible/vars.yml on batcave01.
  files/copr/buildsys.production.priv  SSH private key (prod)    -> private/files/copr/buildsys.production.priv
  files/copr/buildsys.production.pub   SSH public key (prod)    -> public repo + AWS keypairs
  files/copr/buildsys.staging.priv     SSH private key (staging) -> private/files/copr/buildsys.staging.priv
  files/copr/buildsys.staging.pub      SSH public key (staging)  -> public repo
  root-passwords-plaintext.txt      Root passwords in plaintext (DESTROY after rotation)

Deployment order:
  1. Fill in all TODO values in secrets.yml
  2. Merge secrets.yml into /srv/private/ansible/vars.yml
  3. Copy buildsys.{production,staging}.priv to /srv/private/ansible/files/copr/
  4. Commit buildsys.{production,staging}.pub to public ansible repo:
       roles/copr/backend/files/buildsys.{production,staging}.pub
       roles/copr/hypervisor/files/buildsys.{production,staging}.pub
  5. Update AWS EC2 keypairs with new buildsys.production.pub
  6. Run STAGING playbooks first (frontend, backend, dist-git, keygen)
  7. Verify staging (test build)
  8. Run PRODUCTION playbooks (frontend, backend, dist-git, keygen, hypervisor)
    8.1. STOP backend before running playbooks! -> 
      1. set all `max: N` in pools.yaml to `max: 0`
      2. resalloc-maint resource-delete --unused and let the delete requests pass
      3. systemctl stop resalloc copr-backend.target
    8.2. Run playbooks
    8.3. systemctl start copr-backend.target resalloc
  9. Verify production (test build)
 10. Delete old AWS keys, old IBM Cloud key
 11. DESTROY this folder: rm -rf copr-secrets-rotation-*

NOT INCLUDED (separate tickets / external coordination):
  - copr_oidc_*_client_secret (coordinate with IdP team)
  - Pulp mTLS certificates (coordinate with Pulp team)
  - Fedora Messaging certificates (infra messaging team)
EOF

chmod -R go-rwx "${DIR}"

echo ""
echo "==> Done! Created: ${DIR}/"
echo ""
echo "    ${DIR}/secrets.yml"
echo "    ${DIR}/files/copr/buildsys.production.{priv,pub}"
echo "    ${DIR}/files/copr/buildsys.staging.{priv,pub}"
echo "    ${DIR}/root-passwords-plaintext.txt"
echo "    ${DIR}/README.txt"
echo ""
echo "Next steps in README.md"
