#!/bin/bash
# Setup test environment for COPR instance
#
# Usage:
#   setup-local-copr          # Local instance (default)
#   setup-local-copr staging  # Fedora staging
#   setup-local-copr prod     # Fedora production

set -e

TARGET="${1:-local}"

case "$TARGET" in
    local)
        echo "Configuring for local COPR instance..."
        HOSTNAME="frontend"
        PROTOCOL="http"
        PORT="5000"
        COPR_URL="http://frontend:5000"
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
        echo "Usage: $0 [local|staging|prod]"
        exit 1
        ;;
esac

# Configure DNF copr plugin
cat > /etc/dnf/plugins/copr.d/tested-copr.conf << EOF
[tested-copr]
hostname = $HOSTNAME
protocol = $PROTOCOL
port = $PORT
EOF

echo "DNF copr plugin configured:"
cat /etc/dnf/plugins/copr.d/tested-copr.conf
echo ""

echo "=============================================="
echo "Get your API token from: $COPR_URL/api/"
echo ""
echo "Save to ~/.config/copr with copr_url = $COPR_URL"
echo ""
echo "Test with: copr-cli whoami"
echo "=============================================="
