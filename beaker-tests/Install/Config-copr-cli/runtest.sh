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

PACKAGE="tests"

rlJournalStart
    rlPhaseStartSetup
        if [[ ! $RELEASETEST ]]; then
            rlLog "Installing copr dev repos."
            cp ./copr-dev.repo /etc/yum.repos.d/
        fi
        rlLog "Installing copr production repos."
        cp ./copr.repo /etc/yum.repos.d/
        mkdir -p ~/.config || :
        cp ./config ~/.config/copr
        rlRun "dnf config-manager --set-enabled fedora --save"
        rlRun "dnf install -y python3-copr copr-cli"
        rlRun "dnf upgrade python3-copr copr-cli"

        rlLog "Installing repo for DNF with modularity support."
        rlLog "It is disabled though"
        cp ./dnf-modules.repo /etc/yum.repos.d/

        rlAssertRpm copr-cli
    rlPhaseEnd

rlJournalPrintText
rlJournalEnd
