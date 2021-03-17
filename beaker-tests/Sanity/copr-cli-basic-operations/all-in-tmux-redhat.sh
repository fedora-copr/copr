#! /bin/bash

our_dir=$(readlink -f "$(dirname "$0")")

OWNER=$(copr-cli whoami)
FRONTEND_URL=https://dev-copr.devel.redhat.com
BACKEND_URL=https://dev-coprbe.devel.redhat.com
DISTGIT_URL=https://dev-copr-dist-git.devel.redhat.com

set -e

if ! rpm -q rhcopr &>/dev/null; then
    repo='http://coprbe.devel.redhat.com/results/rhcopr-project/toolset/fedora-$releasever-x86_64/'
    dnf install --nogpgcheck -y --repofrompath="rhcopr,$repo" rhcopr
    cp /etc/rhcopr/rh.crt /etc/pki/ca-trust/source/anchors/rh.crt
    update-ca-trust
fi

export OWNER FRONTEND_URL BACKEND_URL DISTGIT_URL
exec "$our_dir/all-in-tmux.sh" "$@"
