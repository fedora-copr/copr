#! /bin/bash
#
# Copyright (c) 2022 Red Hat, Inc.
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
        setupProjectName "PackageNoSources"
    rlPhaseEnd

    rlPhaseStartTest
        # We experienced problem building packages with no sources,
        # please see https://pagure.io/rpkg/issue/604
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        rlRun -s "copr-cli build $PROJECT files/pkg-no-sources.spec "
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
