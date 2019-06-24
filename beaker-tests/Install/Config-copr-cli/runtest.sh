#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/tests/Install/Config-copr-cli
#   Description: Install copr-cli and configure it.
#   Author: Miroslav Suchy <msuchy@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2014 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

HERE=$(dirname "$(realpath "$0")")
PACKAGE="tests"

rlJournalStart
    rlPhaseStartSetup
        if [[ ! $RELEASETEST ]]; then
            rlLog "Installing copr dev repos."
            cp "$HERE/copr-dev.repo" /etc/yum.repos.d/
        fi
        rlLog "Installing copr production repos."
        cp "$HERE/copr.repo" /etc/yum.repos.d/
        mkdir -p ~/.config || :
        rlRun "dnf config-manager --set-enabled fedora --save"
        rlRun "dnf install -y python3-copr copr-cli"
        rlRun "dnf upgrade python3-copr copr-cli"

        cat > /etc/dnf/plugins/copr.d/tested-copr.conf <<EOF
[tested-copr]
hostname = copr-fe-dev.cloud.fedoraproject.org
protocol = https
port = 443
EOF

        rlAssertRpm copr-cli
    rlPhaseEnd

rlJournalPrintText
rlJournalEnd

echo "A manual work is required!"
echo "Please obtain your personal API config from"
echo "https://YOUR_COPR_HOST/api/"
echo "and paste it to the ~/.config/copr"
echo
echo "Create /etc/dnf/plugins/copr.d/tested-copr.conf with contents:"
echo [tested-copr]
echo hostname = YOUR_COPR_HOST
echo protocol = https
echo port = 443
