#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}TestEpel --chroot epel-6-x86_64 --chroot epel-7-x86_64 --chroot epel-8-x86_64 --chroot epel-9-x86_64" 0
        rlRun "copr-cli build ${NAME_PREFIX}TestEpel $HELLO" 0
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}TestEpel"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
