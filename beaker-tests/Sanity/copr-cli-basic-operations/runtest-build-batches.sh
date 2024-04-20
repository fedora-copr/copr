#! /bin/bash
#
# Copyright (c) 2024 Red Hat, Inc.
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
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
        workdirSetup
        setupProjectName "build-batches"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        rlRun -s "copr-cli build $PROJECT $HELLO --nowait"
        rlRun parse_build_id
        BUILD_ID_1=$BUILD_ID

        rlRun -s "copr-cli build $PROJECT $HELLO --with-build-id $BUILD_ID_1 --nowait"
        rlRun parse_build_id
        BUILD_ID_2=$BUILD_ID

        rlRun "copr-cli add-package-scm $PROJECT --name testpkg --clone-url $COPR_HELLO_GIT --method tito"
        rlRun -s "copr-cli build-package $PROJECT --name testpkg --after-build-id $BUILD_ID_1 --nowait"
        rlRun parse_build_id
        BUILD_ID_3=$BUILD_ID

        rlRun "copr watch-build $BUILD_ID_1 $BUILD_ID_2 $BUILD_ID_3"
        rlAssertEquals \
            "All packages succeeded" \
            `copr-cli list-builds $PROJECT |grep succeeded |wc -l` 3
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
