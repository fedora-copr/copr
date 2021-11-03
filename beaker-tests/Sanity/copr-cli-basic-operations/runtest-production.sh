#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest-production.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: A simple post-release test to check whether Copr works
#   Author: Jakub Kadlcik <jkadlcik@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2019 Red Hat, Inc.
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
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"

COPRCONF="/root/.config/copr-production"

if [ ! -f $COPRCONF ]; then
    echo "Error: File $COPRCONF not found!"
    echo "If you want to run this test against the production instance,"
    echo "you must fetch and store your production API token manually."
    echo "For obvious reasons any production config cannot be stored in git."
    exit 1
fi

rlJournalStart
    rlPhaseStartSetup
        rlRun "copr --config $COPRCONF create ${NAME_PREFIX}PostReleaseTest --unlisted-on-hp on --chroot $CHROOT"
    rlPhaseEnd

    rlPhaseStartTest
        # Please do not enhance this file with many other tests.
        # The whole purpose of this file is to have a simple post-release
        # test instead of manually submitting a build.
        # Everything else should be tested only on dev instance.
        rlRun "copr --config $COPRCONF buildscm --clone-url https://src.fedoraproject.org/rpms/copr-cli.git ${NAME_PREFIX}PostReleaseTest"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli --config $COPRCONF delete ${NAME_PREFIX}PostReleaseTest"
    rlPhaseEnd

rlJournalPrintText
rlJournalEnd
