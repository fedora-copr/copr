#!/bin/bash

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"

HELLO=https://frostyx.fedorapeople.org/hello-2.8-1.fc23.src.rpm


rlJournalStart
    rlPhaseStartSetup
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}TestEpel --chroot epel-6-x86_64 --chroot epel-7-x86_64" 0
        rlRun "copr-cli build ${NAME_PREFIX}TestEpel $HELLO" 0
        rlRun "copr-cli delete ${NAME_PREFIX}TestEpel"
    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
