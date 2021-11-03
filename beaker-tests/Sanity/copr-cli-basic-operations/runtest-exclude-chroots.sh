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
        OUTPUT=`mktemp`
        rlRun "copr-cli create --chroot fedora-$FEDORA_VERSION-i386 --chroot fedora-$FEDORA_VERSION-x86_64 --chroot fedora-$FEDORA_VERSION-aarch64 --chroot fedora-rawhide-i386 --chroot fedora-rawhide-x86_64 --chroot fedora-rawhide-aarch64 ${NAME_PREFIX}ExcludeChroots"

        rlRun -s "copr-cli build --nowait --exclude-chroot fedora-$FEDORA_VERSION-aarch64 --exclude-chroot fedora-rawhide-x86_64 ${NAME_PREFIX}ExcludeChroots ${HELLO}"
        rlRun "parse_build_id"
        rlRun "curl $FRONTEND_URL/api_3/build/$BUILD_ID |jq .chroots > $OUTPUT"
        rlRun "cat $OUTPUT |grep fedora-$FEDORA_VERSION-x86_64"
        rlRun "cat $OUTPUT |grep fedora-$FEDORA_VERSION-aarch64" 1
        rlAssertEquals "Make sure the correct number of chroots is enabled" "`jq length $OUTPUT`" 4
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli cancel $BUILD_ID"
        rlRun "copr-cli delete ${NAME_PREFIX}ExcludeChroots"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
