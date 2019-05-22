#! /bin/bash
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Sanity/auto-prune
#   Description: Tests that --auto-prune works in cli.
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
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"

assert_auto_prune ()
{
    rlRun -s "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}AutoPrune/detail/" 0
    rlRun "auto_prune=$(jq .detail.auto_prune < "$rlRun_LOG")"
    rlAssertEquals "auto prune is $1" "$auto_prune" "$1"
}

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm "copr-cli"
        rlAssertRpm "jq"
        rlAssertExists ~/.config/copr
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --auto-prune off --chroot $CHROOT ${NAME_PREFIX}AutoPrune"
        assert_auto_prune false
        rlRun "copr-cli modify --auto-prune on ${NAME_PREFIX}AutoPrune"
        assert_auto_prune true
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}AutoPrune"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
