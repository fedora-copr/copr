#! /bin/bash
#
# Copyright (c) 2022 Red Hat, Inc.
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

PYPI_PACKAGE="pello"
PACKAGE="test_package_pypi"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        setupProjectName "Pyp2spec"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"

        # Submit pyp2spec build directly
        rlRun "copr-cli buildpypi $PROJECT --packagename $PYPI_PACKAGE --spec-generator pyp2spec"

        # Create pyp2spec package
        rlRun "copr-cli add-package-pypi $PROJECT --name $PACKAGE --packagename $PYPI_PACKAGE --spec-generator pyp2spec"

        # Build the package
        rlRun -s "copr-cli build-package --name $PACKAGE $PROJECT -r $CHROOT --nowait"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        # rlRun "copr-cli download-build $BUILD_ID"
        rlRun "wget $BACKEND_URL/results/$PROJECT/srpm-builds/$(printf %08d "$BUILD_ID")/builder-live.log.gz"
        rlRun "gzip -fd builder-live.log.gz"
        rlRun "head builder-live.log -n 50 |grep spec_generator |grep pyp2spec"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
