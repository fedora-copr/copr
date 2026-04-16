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
        setupProjectName "storage"
    rlPhaseEnd

    rlPhaseStartTest
        # The point of this file was to have a minimal set of tests that is
        # run against all supported storages. However, some Copr instances
        # don't use Pulp and therefore it doesn't make sense to run this
        # test against them. This is all a temporary situation anyway,
        # the proper way of doing things is going to be
        # https://github.com/fedora-copr/copr/issues/4205
        # and we are going to run the full beaker test suite there
        if [[ $STORAGE == "backend" ]]; then
            rlLog "Skipping, this Copr instance doesn't use Pulp"
            exit 0
        fi

        for storage in "backend" "pulp"; do
            project="$PROJECT-$storage"
            rlRun "copr-cli create --chroot $CHROOT $project --storage $storage"

            rlRun -s "copr-cli build $project $HELLO --nowait"
            rlRun parse_build_id
            rlRun "copr watch-build $BUILD_ID"

            rlRun "yes | dnf copr enable $DNF_COPR_ID/$project $CHROOT"
            rlRun "dnf install -y hello"
            rlAssertRpm "hello"
            rlRun "dnf remove hello -y"
            rlRun "yes | dnf copr remove $DNF_COPR_ID/$project"
        done
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "$project"
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
