#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

PACKAGE="https://raw.githubusercontent.com/fedora-copr/test-data-copr-backend/main/to_prune/00999998-dummy-pkg/dummy-pkg-2-1.fc34.src.rpm"

CHROOTS="  --chroot openmandriva-cooker-aarch64"
CHROOTS+=" --chroot openmandriva-cooker-x86_64"
CHROOTS+=" --chroot openmandriva-rolling-aarch64"
CHROOTS+=" --chroot openmandriva-rolling-x86_64"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        # https://github.com/fedora-copr/copr/issues/3433
        # https://github.com/rpm-software-management/mock/issues/1066
        echo "OpenMandriva are known to be broken. Skipping."
        exit 0
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
