#! /bin/bash
#
# Copyright (c) 2021 Red Hat, Inc.
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
    rlPhaseEnd

    rlPhaseStartTest
        # Create a project with appstream option turned on, and make sure
        # it is generated into the repodata
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Appstream --appstream off"
        rlRun -s "copr-cli build ${NAME_PREFIX}Appstream ${HELLO}"
        rlRun "curl $BACKEND_URL/results/${NAME_PREFIX}Appstream/$CHROOT/repodata/repomd.xml |grep location |grep appstream.xml" 1

        # Modify the project and enable the appstream generation
        rlRun "copr-cli modify ${NAME_PREFIX}Appstream --appstream on"
        rlRun -s "copr-cli build ${NAME_PREFIX}Appstream ${HELLO}"
        rlRun "curl $BACKEND_URL/results/${NAME_PREFIX}Appstream/$CHROOT/repodata/repomd.xml |grep location |grep appstream.xml"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}Appstream"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
