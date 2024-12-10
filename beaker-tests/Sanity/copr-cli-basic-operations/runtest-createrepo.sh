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
        # don't specify chroot here, rely on auto-detection
        rlRun "dnf -y copr enable ${URL}/${NAME_PREFIX}Createrepo"
        rlRun "dnf --disablerepo='*' \
            --enablerepo='copr:${URL}:$(repo_owner):${NAME_VAR}Createrepo' \
            list available 2>&1 | grep 'Failed to synchronize'" 1

        rlRun "copr-cli modify ${NAME_PREFIX}Createrepo --chroot fedora-rawhide-x86_64"

        echo "wait 2+ minutes to invalidate cache"
        echo "https://github.com/fedora-copr/copr/blob/526473b43b5e0c1f84f7db624f349a50a8e2b7d9/frontend/coprs_frontend/coprs/views/apiv3_ns/apiv3_rpmrepo.py#L37"
        sleep 125
        rlRun "dnf -y copr enable ${URL}/${NAME_PREFIX}Createrepo fedora-rawhide-x86_64"
        rlRun "dnf --disablerepo='*' \
            --enablerepo='copr:${URL}:$(repo_owner):${NAME_VAR}Createrepo' \
            list available 2>&1 | grep 'Failed to synchronize'" 1
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}Createrepo"
        rlRun "dnf -y copr remove ${URL}/${NAME_PREFIX}Createrepo"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
