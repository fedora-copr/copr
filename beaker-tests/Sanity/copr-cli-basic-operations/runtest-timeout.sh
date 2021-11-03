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
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Timeout"
        rlRun -s "copr-cli build --timeout 72500 ${NAME_PREFIX}Timeout $HELLO"
        rlRun "parse_build_id"
        rlRun "curl $FRONTEND_URL/backend/get-build-task/$BUILD_ID-$CHROOT | jq .timeout"
        rlRun "BUILD_TIMEOUT=$(curl "$FRONTEND_URL"/backend/get-build-task/"$BUILD_ID"-"$CHROOT" | jq .timeout)"
        rlAssertEquals "Test that timeout is set to 72500" "$BUILD_TIMEOUT" 72500

        rlRun "SRPM=$(rpmbuild -bs "$HERE"/files/test-timeout.spec |grep Wrote: |cut -d ' ' -f2)"
        rlRun -s "copr-cli build --timeout 10 ${NAME_PREFIX}Timeout $SRPM" 4
        rlRun "parse_build_id"
        LOG=`mktemp`
        log_file="$BACKEND_URL/results/${NAME_PREFIX}Timeout/$CHROOT/$(build_id_with_leading_zeroes)-test-timeout/builder-live.log.gz"
        curl "$log_file" | gunzip > "$LOG"
        rlAssertEquals "timeout in log" `cat $LOG | grep 'sending INT' |wc -l` 1
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}Timeout"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
