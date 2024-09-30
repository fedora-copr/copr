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
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}BuildSpec --enable-net on --chroot $CHROOT" 0
        rlRun "copr-cli build ${NAME_PREFIX}BuildSpec $HERE/files/enum.spec" 0

        # Make sure we don't upload SRPM/Spec if user tries to build into
        # a non-existing project (or project he doesn't have permissions to)
        OUTPUT=`mktemp`
        rlRun "copr-cli build --nowait ${NAME_PREFIX}NonExisting $HERE/files/enum.spec &> $OUTPUT" 1
        rlAssertEquals "" `grep -r 'does not exist' $OUTPUT |wc -l` 1
        rlAssertEquals "" `grep -r 'Uploading package' $OUTPUT |wc -l` 0

        # Or a non-existing and invalid CoprDir
        OUTPUT=`mktemp`
        rlRun "copr-cli build --nowait ${NAME_PREFIX}BuildSpec:foo $HERE/files/enum.spec &> $OUTPUT" 1
        rlAssertEquals "" `grep -r "Please use directory format" $OUTPUT |wc -l` 1
        rlAssertEquals "" `grep -r 'Uploading package' $OUTPUT |wc -l` 0

        # Or a non-existing chroot
        OUTPUT=`mktemp`
        rlRun "copr-cli build --nowait ${NAME_PREFIX}BuildSpec --chroot foo $HERE/files/enum.spec &> $OUTPUT" 1
        rlAssertEquals "" `grep -r 'not a valid choice' $OUTPUT |wc -l` 1
        rlAssertEquals "" `grep -r 'Uploading package' $OUTPUT |wc -l` 0

        # TODO Check that we don't upload if we don't have permissions for the
        # project. It's hard to do so because we run beaker tests under admin
        # users (some other tests require it).

    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}BuildSpec"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
