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
        setupProjectName "build-attributes"
    rlPhaseEnd

    rlPhaseStartTest
        ## Test package listing attributes
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        rlRun "copr-cli add-package-scm $PROJECT --name example --clone-url $COPR_HELLO_GIT"

        OUTPUT=`mktemp`
        rlLog "Temporary output file is $OUTPUT"

        BUILDS=`mktemp`
        LATEST_BUILD=`mktemp`
        LATEST_SUCCEEDED_BUILD=`mktemp`

        # run the tests before build
        rlRun "copr-cli get-package $PROJECT --name example --with-all-builds --with-latest-build --with-latest-succeeded-build > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Builds are empty" "`cat $BUILDS`" '[]'
        rlAssertEquals "There is no latest build." "`cat $LATEST_BUILD`" 'null'
        rlAssertEquals "And there is no latest succeeded build." "`cat $LATEST_SUCCEEDED_BUILD`" 'null'

        TMP=`mktemp -d`
        # run the build and wait
        rlRun "copr-cli buildscm --clone-url $COPR_HELLO_GIT $PROJECT --commit rpkg-util | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > $TMP/succeeded_example_build_id"

        # This build should fail (but still we have to be able to create source
        # RPM from git, so no artificial commit hashes here).  The
        # 'rpkg-util-fail-rpm branch' contains sources without 'git'
        # in BuildRequires;  so on F30+ this build fails since there's
        # no gcc compiler.
        rlRun "copr-cli buildscm --clone-url $COPR_HELLO_GIT --commit rpkg-util-fail-rpm $PROJECT | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > $TMP/failed_example_build_id"

        # run the tests after build
        rlRun "copr-cli get-package $PROJECT --name example --with-all-builds --with-latest-build --with-latest-succeeded-build > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Build list contain two builds" `cat $BUILDS | jq '. | length'` 2
        rlAssertEquals "The latest build is the failed one." `cat $LATEST_BUILD | jq '.id'` `cat $TMP/failed_example_build_id`
        rlAssertEquals "The latest succeeded build is also correctly returned." `cat $LATEST_SUCCEEDED_BUILD | jq '.id'` `cat $TMP/succeeded_example_build_id`

        # run the same tests for list-packages cmd and its first (should be the only one) result
        rlRun "copr-cli list-packages $PROJECT --with-all-builds --with-latest-build --with-latest-succeeded-build | jq '.[0]' > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Build list contain two builds" `cat $BUILDS | jq '. | length'` 2
        rlAssertEquals "The latest build is the failed one." `cat $LATEST_BUILD | jq '.id'` `cat $TMP/failed_example_build_id`
        rlAssertEquals "The latest succeeded build is also correctly returned." `cat $LATEST_SUCCEEDED_BUILD | jq '.id'` `cat $TMP/succeeded_example_build_id`
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
