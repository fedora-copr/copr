#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: Tests basic operations of copr using copr-cli.
#   Author: Silvie Chlupova <schlupov@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2020 Red Hat, Inc.
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
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Isolation"
        rlRun -s "copr-cli build --isolation simple ${NAME_PREFIX}Isolation $HELLO"
        rlRun "parse_build_id"
        rlRun "curl $FRONTEND_URL/backend/get-build-task/$BUILD_ID-$CHROOT | jq .isolation"
        rlRun "BUILD_ISOLATION=$(curl "$FRONTEND_URL"/backend/get-build-task/"$BUILD_ID"-"$CHROOT" | jq .isolation)"
        rlAssertEquals "Test that isolation is set to simple" "$BUILD_ISOLATION" "simple"

        rlRun -s "copr-cli build ${NAME_PREFIX}Isolation $HELLO"
        rlRun "parse_build_id"
        rlRun "curl $FRONTEND_URL/backend/get-build-task/$BUILD_ID-$CHROOT | jq .isolation"
        rlRun "BUILD_ISOLATION=$(curl "$FRONTEND_URL"/backend/get-build-task/"$BUILD_ID"-"$CHROOT" | jq .isolation)"
        rlAssertEquals "Test that isolation is set to default" "$BUILD_ISOLATION" "default"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}Isolation"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
