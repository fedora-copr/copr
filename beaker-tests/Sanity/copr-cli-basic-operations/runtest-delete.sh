#! /bin/bash
#
# Copyright (c) 2020 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/.


# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm "copr-cli"
        rlAssertRpm "jq"
        rlAssertExists ~/.config/copr
        TMP=$(mktemp -d)
    rlPhaseEnd

    rlPhaseStartTest
        # Bug 1368259 - Deleting a build from a group project doesn't delete backend files
        rlRun "copr-cli create ${NAME_PREFIX}TestDeleteGroupBuild --chroot $CHROOT" 0
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}TestDeleteGroupBuild --name example --clone-url $COPR_HELLO_GIT"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestDeleteGroupBuild | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > $TMP/TestDeleteGroupBuild_example_build_id.txt"
        BUILD_ID=$(cat "$TMP"/TestDeleteGroupBuild_example_build_id.txt)

        chroot_url=$BACKEND_URL/results/${NAME_PREFIX}TestDeleteGroupBuild/$CHROOT
        check_url=$chroot_url/$(printf "%08d" "$BUILD_ID")-example
        rlRun "curl -f $check_url" 0 "check that the directory still exists"
        rlRun "copr-cli delete-package --name example ${NAME_PREFIX}TestDeleteGroupBuild"
        i=0
        while curl -f "$check_url"; do
            sleep 2
            i=$(( i + 2 ))
            test "$i" -gt 60 && break
        done
        rlAssertGreater "Check that we did not wait longer than 60s" 60 "$i"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}TestDeleteGroupBuild"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
