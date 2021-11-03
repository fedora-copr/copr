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
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        # and install... things
        yum -y install dnf dnf-plugins-core
        # use the dev instance
        sed -i "s+http://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
        sed -i "s+https://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
    rlPhaseEnd

    rlPhaseStartTest
        # Test for https://pagure.io/copr/copr/issue/67
        rlRun "copr-cli create ${NAME_PREFIX}TestBugPagure67 --chroot $CHROOT" 0
        # The issue #67 specifically concerns the *-package-tito commands,
        # but since they were deprecated and even removed from the code,
        # we are going to use its successor for this test
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}TestBugPagure67 --name test_package_tito --clone-url $COPR_HELLO_GIT --method tito_test --webhook-rebuild on --commit foo --subdir bar"
        OUTPUT=`mktemp`
        rlRun "copr-cli get-package ${NAME_PREFIX}TestBugPagure67 --name test_package_tito > $OUTPUT"
        rlAssertEquals "" `cat $OUTPUT | jq '.auto_rebuild'` "true"
        rlRun "copr-cli edit-package-scm ${NAME_PREFIX}TestBugPagure67 --name test_package_tito --clone-url $COPR_HELLO_GIT --method tito_test --commit foo --subdir bar"
        rlRun "copr-cli get-package ${NAME_PREFIX}TestBugPagure67 --name test_package_tito > $OUTPUT"
        rlAssertEquals "" `cat $OUTPUT | jq '.auto_rebuild'` "true"
        rlRun "copr-cli delete ${NAME_PREFIX}TestBugPagure67"
        rm $OUTPUT
    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
