#!/bin/bash

. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

URL=${FRONTEND_URL#https://}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}Createrepo --chroot $CHROOT"
        echo "sleep 60 seconds to give backend enough time to generate the repo"
        sleep 60
        # don't specify chroot here, rely on auto-detection
        rlRun "dnf -y copr enable ${URL}/${NAME_PREFIX}Createrepo"
        rlRun "dnf --disablerepo='*' \
            --enablerepo='copr:${URL}:$(repo_owner):${NAME_VAR}Createrepo' \
            list available 2>&1 | grep 'Failed to synchronize'" 1

        rlRun "copr-cli modify ${NAME_PREFIX}Createrepo --chroot fedora-rawhide-x86_64"
        echo "sleep 60 seconds to give backend enough time to generate the repo"
        sleep 60
        rlRun "dnf -y copr enable ${URL}/${NAME_PREFIX}Createrepo fedora-rawhide-x86_64"
        rlRun "dnf --disablerepo='*' \
            --enablerepo='copr:${URL}:$(repo_owner):${NAME_VAR}Createrepo' \
            list available 2>&1 | grep 'Failed to synchronize'" 1
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}Createrepo"
        rlRun "dnf -y copr remove ${URL}/${NAME_PREFIX}Createrepo"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
