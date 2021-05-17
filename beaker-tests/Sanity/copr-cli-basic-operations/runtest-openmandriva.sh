#!/bin/bash

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

PACKAGE="http://abf-downloads.openmandriva.org/cooker/repository/SRPMS/main/release/python-pip-21.0.1-1.src.rpm"
CHROOTS="  --chroot openmandriva-cooker-aarch64"
CHROOTS+=" --chroot openmandriva-cooker-i686"
CHROOTS+=" --chroot openmandriva-cooker-x86_64"
CHROOTS+=" --chroot openmandriva-rolling-aarch64"
CHROOTS+=" --chroot openmandriva-rolling-i686"
CHROOTS+=" --chroot openmandriva-rolling-x86_64"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}TestOpenMandriva $CHROOTS" 0
        rlRun "copr-cli build ${NAME_PREFIX}TestOpenMandriva $PACKAGE" 0
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}TestOpenMandriva"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
