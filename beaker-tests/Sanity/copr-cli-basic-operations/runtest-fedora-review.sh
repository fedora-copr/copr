#! /bin/bash
#
# Copyright (c) 2021 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/.


# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


result_file()
{
    # _file="$BACKEND_URL/results/${NAME_PREFIX}FedoraReview/$CHROOT/$(build_id_with_leading_zeroes)/$1"
    # rlLog "fetching $_file"
    # curl "$_file"
    "$BACKEND_URL/results/${NAME_PREFIX}FedoraReview/$CHROOT/$(build_id_with_leading_zeroes)/$1"
}


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
    rlPhaseEnd

    rlPhaseStartTest
        # Create a project with fedora review option turned on, and make sure
        # it produced some output
        resultdir=`mktemp -d`
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}FedoraReview --fedora-review"
        rlRun -s "copr-cli build ${NAME_PREFIX}FedoraReview ${HELLO} --nowait"
	rlRun "parse_build_id"
	rlRun "copr watch-build $BUILD_ID"
	rlRun "wget -P $resultdir $BACKEND_URL/results/${NAME_PREFIX}FedoraReview/$CHROOT/$(build_id_with_leading_zeroes)-hello/fedora-review/review.txt"
	rlRun "[ -s $resultdir/review.txt ]"

	# Modify the project and disable fedora review option and see that
	# the tool didn't run
        rlRun "copr-cli modify ${NAME_PREFIX}FedoraReview --fedora-review off"
        rlRun -s "copr-cli build ${NAME_PREFIX}FedoraReview ${HELLO} --nowait"
	rlRun "parse_build_id"
	rlRun "copr watch-build $BUILD_ID"
	rlRun "wget -P $resultdir $BACKEND_URL/results/${NAME_PREFIX}FedoraReview/$CHROOT/$(build_id_with_leading_zeroes)-hello/fedora-review/" 8
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}FedoraReview"
	rlRun "rm -rf $resultdir/*"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
