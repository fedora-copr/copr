#!/bin/bash

# test for rhbz#1691553

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        setupProjectName make-srpm-fail
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create $PROJECT --chroot $CHROOT" 0

        rlRun -s "copr-cli buildscm --method make_srpm \
--clone-url https://pagure.io/copr/copr-hello.git \
--commit noluck-make-srpm $PROJECT" 4
        rlRun parse_build_id
        output=$(get_srpm_builder_log | grep "^stderr output$")
        rlAssertEquals "Check 'stderr output' string is in output" "stderr output" "$output"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
