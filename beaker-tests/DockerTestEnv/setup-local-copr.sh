#!/bin/bash
# Setup test environment for COPR instance
#
# Usage:
#   setup-local-copr local-kube       # Podman kube play instance (default)
#   setup-local-copr local-openshift  # Local OpenShift/CRC instance
#   setup-local-copr staging         # Fedora staging
#   setup-local-copr prod            # Fedora production
#   setup-local-copr --auto-token    # Add to any target to auto-configure API token

set -e

AUTO_TOKEN=false
TARGET="local-kube"

for arg in "$@"; do
    case $arg in
        --auto-token) AUTO_TOKEN=true ;;
        *)            TARGET="$arg" ;;
    esac
done

case $TARGET in
    local-kube)
        echo "Configuring for podman kube play COPR instance..."
        HOSTNAME="frontend"
        PROTOCOL="http"
        PORT="5000"
        COPR_URL="http://frontend:5000"
        ;;
    local-openshift)
        echo "Configuring for local OpenShift/CRC COPR instance..."
        HOSTNAME="copr-frontend-copr.apps.crc.testing"
        PROTOCOL="http"
        PORT="80"
        COPR_URL="http://copr-frontend-copr.apps.crc.testing"
        ;;
    staging|stg)
        echo "Configuring for Fedora COPR staging..."
        HOSTNAME="copr.stg.fedoraproject.org"
        PROTOCOL="https"
        PORT="443"
        COPR_URL="https://copr.stg.fedoraproject.org"
        ;;
    prod|production)
        echo "Configuring for Fedora COPR production..."
        HOSTNAME="copr.fedorainfracloud.org"
        PROTOCOL="https"
        PORT="443"
        COPR_URL="https://copr.fedorainfracloud.org"
        ;;
    *)
        echo "Unknown target: $TARGET"
        echo "Usage: $0 [local-kube|local-openshift|staging|prod] [--auto-token]"
        exit 1
        ;;
esac

# Configure DNF copr plugin.
#
# Two sections are written for the same target, keyed differently:
#   - [tested-copr]  lets tests use the short alias (DNF_COPR_ID=tested-copr,
#     e.g. `dnf copr enable tested-copr/user/project`).
#   - [$HOSTNAME]    is needed because dnf-plugins-core resolves the "hub" in
#     the `hub/user/project` form by looking up a config section whose NAME
#     equals the hub string.
cat > /etc/dnf/plugins/copr.d/tested-copr.conf << EOF
[tested-copr]
hostname = $HOSTNAME
protocol = $PROTOCOL
port = $PORT

[$HOSTNAME]
hostname = $HOSTNAME
protocol = $PROTOCOL
port = $PORT
EOF

echo "DNF copr plugin configured:"
cat /etc/dnf/plugins/copr.d/tested-copr.conf

if $AUTO_TOKEN; then
    # --auto-token expects API_LOGIN, API_TOKEN, USERNAME env vars to be set
    # (injected by the MCP test_env_up tool or manually)
    if [ -z "$API_LOGIN" ] || [ -z "$API_TOKEN" ]; then
        echo "ERROR: --auto-token requires API_LOGIN and API_TOKEN env vars" >&2
        echo "Use: API_LOGIN=... API_TOKEN=... setup-local-copr --auto-token" >&2
        echo "Or let the MCP test_env_up() tool handle this automatically." >&2
        exit 1
    fi

    USERNAME="${USERNAME:-jdoe}"
    ENCRYPTED="true"
    [ "$PROTOCOL" = "http" ] && ENCRYPTED="false"

    mkdir -p ~/.config
    cat > ~/.config/copr << COPR_EOF
[copr-cli]
login = $API_LOGIN
username = $USERNAME
token = $API_TOKEN
copr_url = $COPR_URL
encrypted = $ENCRYPTED
COPR_EOF

    echo "API token written to ~/.config/copr"
    echo "User: $USERNAME"
    copr-cli whoami
else
    echo ""
    echo "Get your API token from: $COPR_URL/api/"
    echo "Save to ~/.config/copr with copr_url = $COPR_URL"
    echo "Test with: copr-cli whoami"
fi
