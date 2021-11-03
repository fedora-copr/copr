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
        # This may be a controversial place to test DNF copr plugin but I think
        # it is a good idea to have a couple of simple tests within a Copr
        # codebase.
        #
        # DNF copr plugin (intentionally) doesn't use python3-copr and calls API
        # endpoints directly. When API endpoints get deprecated or removed, we
        # might forget to fix the DNF copr plugin and make it unusable after
        # such Copr release.
        #
        # This will help us discover such issues soon enough to fix them.

        OUTPUT=`mktemp`

        # Test `dnf copr search' command
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}DnfCopr"
        rlRun "dnf copr --hub tested-copr search ${NAME_PREFIX}DnfCopr > $OUTPUT"
        rlRun "cat $OUTPUT |grep '${NAME_PREFIX}DnfCopr' |grep 'No description given'"

        # Test `dnf copr list' command
        rlRun "dnf copr list > $OUTPUT"
        rlRun "cat $OUTPUT |grep 'copr.fedorainfracloud.org/group_copr/copr'"
        rlRun "cat $OUTPUT |grep 'copr.fedorainfracloud.org/group_copr/copr-dev'"

        # Test `dnf copr enable' command
        rlRun "copr-cli build ${NAME_PREFIX}DnfCopr ${HELLO}"
        rlRun "dnf -y copr enable --hub tested-copr ${NAME_PREFIX}DnfCopr"
        rlRun "dnf -y install hello"
        rlRun "hello"
        rlRun "dnf -y erase hello"

        # Test `dnf copr list --available-by-user' command
        rlRun "dnf copr --hub tested-copr list --available-by-user $OWNER > $OUTPUT"
        rlRun "cat $OUTPUT |grep '${NAME_PREFIX}DnfCopr' |grep 'No description given'"

        # Test `dnf copr disable' command
        rlRun "dnf -y copr disable --hub tested-copr ${NAME_PREFIX}DnfCopr"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}DnfCopr"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
