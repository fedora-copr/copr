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

modify_chroot()
{
    copr-cli edit-chroot $PROJECT/$CHROOT \
         --isolation simple \
         --modules "foo:bar" \
         --packages "foo bar baz" \
         --rpmbuild-with="--foo"
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
        workdirSetup
        setupProjectName "ResetToDefaults"
    rlPhaseEnd

    rlPhaseStartTest
        # Create an empty project and save the chroot defaults
        tmp1=$(mktemp -p ./)
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT > $tmp1"

        # Modify the chroot and configure various options
        tmp=$(mktemp -p ./)
        rlRun "modify_chroot"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT > $tmp"
        rlRun "jq -e '.additional_packages == [\"foo\", \"bar\", \"baz\"]' $tmp"
        rlRun "jq -e '.additional_modules == [\"foo:bar\"]' $tmp"
        rlRun "jq -e '.isolation == \"simple\"' $tmp"
        rlRun "jq -e '.with_opts == [\"--foo\"]' $tmp"

        # Reset one field and make sure the rest of them remain unchanged
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --reset additional_packages"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT > $tmp"
        rlRun "jq -e '.additional_packages == []' $tmp"
        rlRun "jq -e '.additional_modules == [\"foo:bar\"]' $tmp"
        rlRun "jq -e '.isolation == \"simple\"' $tmp"
        rlRun "jq -e '.with_opts == [\"--foo\"]' $tmp"

        # Reset another field
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --reset additional_modules"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT > $tmp"
        rlRun "jq -e '.additional_modules == []' $tmp"
        rlRun "jq -e '.isolation == \"simple\"' $tmp"
        rlRun "jq -e '.with_opts == [\"--foo\"]' $tmp"

        # Reset multiple fields at once
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --reset isolation --reset with_opts"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT > $tmp"
        rlRun "jq -e '.isolation == \"unchanged\"' $tmp"
        rlRun "jq -e '.with_opts == []' $tmp"

        # When all fields have been reseted, make sure the chroot is exactly
        # same as when it was fresh
        rlRun "diff $tmp1 $tmp"

        # Try to reset a non-existing field
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --reset nonexisting &> $tmp" 1
        rlRun "cat $tmp |grep 'Trying to reset an invalid attribute: nonexisting'"
        rlRun "cat $tmp |grep \"copr-cli get-chroot $PROJECT/$CHROOT' for all the possible attributes\""
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
