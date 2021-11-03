#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest-modules.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: Tests basic operations of copr using copr-cli.
#   Author: clime <clime@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2021 Red Hat, Inc.
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
source "$HERE/helpers"

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}BuildSpecNetworking --chroot $CHROOT" 0
        rlRun -s "copr-cli build ${NAME_PREFIX}BuildSpecNetworking --enable-net on $HERE/files/vera.spec --nowait" 0
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"
        rlRun "curl $FRONTEND_URL/backend/get-build-task/$BUILD_ID-$CHROOT | jq .enable_net"
        rlRun "BUILD_ENABLE_NET=$(curl "$FRONTEND_URL"/backend/get-build-task/"$BUILD_ID"-"$CHROOT" | jq .enable_net)"
        rlAssertEquals "Test that networking is enabled" "$BUILD_ENABLE_NET" "true"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}BuildSpecNetworking"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
