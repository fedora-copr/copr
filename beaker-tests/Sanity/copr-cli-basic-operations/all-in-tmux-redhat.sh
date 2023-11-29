#! /bin/bash

our_dir=$(readlink -f "$(dirname "$0")")

OWNER=$(copr-cli whoami)
FRONTEND_HOST=dev-copr.devel.redhat.com
FRONTEND_URL=https://$FRONTEND_HOST
BACKEND_URL=https://dev-coprbe.devel.redhat.com
DISTGIT_URL=https://dev-copr-dist-git.devel.redhat.com
VENDOR="Red Hat Internal Copr (devel) - "
DISTGIT_BRANCH_FEDORA_PREFIX=fedora/

set -e

if ! rpm -q rhcopr &>/dev/null; then
    repo='http://coprbe.devel.redhat.com/results/rhcopr-project/toolset/fedora-$releasever-x86_64/'
    dnf install --nogpgcheck -y --repofrompath="rhcopr,$repo" rhcopr
    cp /etc/rhcopr/rh.crt /etc/pki/ca-trust/source/anchors/rh.crt
    update-ca-trust

    cat > /etc/dnf/plugins/copr.d/tested-copr.conf <<EOF
[tested-copr]
hostname = $FRONTEND_HOST
protocol = https
port = 443
EOF

fi

export OWNER FRONTEND_URL BACKEND_URL DISTGIT_URL VENDOR DISTGIT_BRANCH_FEDORA_PREFIX
exec "$our_dir/all-in-tmux.sh" "$@"
