#! /bin/bash
#
# Copyright (c) 2019-2022 Red Hat, Inc.
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
        setupProjectName "Architectures"
    rlPhaseEnd

    rlPhaseStartTest
        # We support aarch64 both in Red Hat and Fedora Copr
        chroots=(
            --chroot "fedora-$FEDORA_VERSION-aarch64"
        )

        case $FRONTEND_URL in
        *fedora*.org*)
            chroots+=(
                --chroot "fedora-$FEDORA_VERSION-s390x"
                --chroot "fedora-$FEDORA_VERSION-ppc64le"
                --chroot "epel-9-ppc64le"
            )
            ;;
        esac

        rlRun "copr-cli create ${chroots[*]} $PROJECT"
        rlRun "copr-cli build $PROJECT ${HELLO}"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
