#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest-modules.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: Tests basic operations of copr using copr-cli.
#   Author: clime <clime@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2014 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"


rlJournalStart
    rlPhaseStartSetup
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr create ${NAME_PREFIX}BuildScm --enable-net on --chroot $CHROOT" 0
        rlRun "copr buildscm --clone-url https://src.fedoraproject.org/rpms/rpkg-util.git ${NAME_PREFIX}BuildScm" 0
        rlRun "copr buildscm --clone-url https://github.com/clime/example.git --method make_srpm ${NAME_PREFIX}BuildScm" 0
        rlRun "copr buildscm --clone-url https://github.com/clime/example.git --method tito ${NAME_PREFIX}BuildScm" 0
        rlRun "copr buildscm --clone-url https://github.com/clime/example2.git --subdir subpkg --spec example.spec --method tito_test ${NAME_PREFIX}BuildScm" 0
        rlRun "copr buildscm --clone-url https://src.fedoraproject.org/forks/mgahagan/rpms/passwd.git --commit 9ac07e38c9351fb1c4e724e68deaeac6b6b1ab4 ${NAME_PREFIX}BuildScm" 0

        rlRun "copr create ${NAME_PREFIX}PackageScm --enable-net on --chroot $CHROOT" 0
        rlRun "copr add-package-scm --name example --clone-url https://github.com/clime/example.git --method tito ${NAME_PREFIX}PackageScm" 0
        rlRun "copr edit-package-scm --name example --clone-url https://github.com/clime/example.git --method rpkg ${NAME_PREFIX}PackageScm" 0
        rlRun "copr build-package --name example ${NAME_PREFIX}PackageScm" 0

        rlRun "copr-cli delete ${NAME_PREFIX}BuildScm"
        rlRun "copr-cli delete ${NAME_PREFIX}PackageScm"
    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
