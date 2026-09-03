#! /bin/bash
#
# Copyright (c) 2024 Red Hat, Inc.
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

# The "pello" package was previously included here but did not conform
# to PEP 625 standards.
PYPI_PACKAGE="pyp2spec"
PACKAGE_OVERRIDE=test_package_pypi

# TODO: Test PEP 625 non-compliant package.  Refer to #3517 discussion.

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        workdirSetup
        setupProjectName "Pyp2spec"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"

        # Submit pyp2spec build directly, generates python-pyp2spec package
        rlRun "copr-cli buildpypi $PROJECT --packagename $PYPI_PACKAGE --spec-generator pyp2spec"

        # Create pyp2spec package, not python-pyp2spec
        rlRun "copr-cli add-package-pypi $PROJECT --name pyp2spec --packagename $PYPI_PACKAGE --spec-generator pyp2spec"

        # Build the package
        rlRun -s "copr-cli build-package --name pyp2spec $PROJECT -r $CHROOT --nowait"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        # rlRun "copr-cli download-build $BUILD_ID"
        rlRun "wget $BACKEND_URL/results/$PROJECT/srpm-builds/$(printf %08d "$BUILD_ID")/builder-live.log.gz"
        rlRun "gzip -fd builder-live.log.gz"
        rlRun "head builder-live.log -n 50 |grep spec_generator |grep pyp2spec"

        OUTPUT=output-file.log
        SOURCE_DICT=source-dict.json

        # PyPI package creation, pyp2spec building itself
        rlRun "copr-cli add-package-pypi $PROJECT --name $PACKAGE_OVERRIDE --packagename pyp2rpm --spec-generator pyp2spec --packageversion 1.0.4"
        rlRun "copr-cli get-package $PROJECT --name $PACKAGE_OVERRIDE > $OUTPUT"
        rlRun "cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT"
        rlAssertEquals "package.name == \"$PACKAGE_OVERRIDE\"" `cat $OUTPUT | jq '.name'` "\"$PACKAGE_OVERRIDE\""
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlAssertEquals "package.source_dict.pypi_package_name == \"pyp2rpm\"" `cat $SOURCE_DICT | jq '.pypi_package_name'` '"pyp2rpm"'
        rlAssertEquals "package.source_dict.pypi_package_version == \"bar\"" `cat $SOURCE_DICT | jq '.pypi_package_version'` '"1.0.4"'
        rlAssertEquals "package.source_dict.spec_generator == \"pyp2spec\"" `cat $SOURCE_DICT | jq '.spec_generator'` '"pyp2spec"'

        # PyPI package modification.
        # - reset the copr package to a different PyPI project
        # - reset (implicitly) to pyp2spec generator by default https://github.com/fedora-copr/copr/issues/3523
        rlRun "copr-cli edit-package-pypi $PROJECT --name $PACKAGE_OVERRIDE --packagename pello"
        rlRun "copr-cli get-package $PROJECT --name $PACKAGE_OVERRIDE > $OUTPUT"
        jq '.source_dict' < "$OUTPUT" > "$SOURCE_DICT"
        rlAssertEquals "package.name == \"$PACKAGE_OVERRIDE\"" `cat $OUTPUT | jq '.name'` "\"$PACKAGE_OVERRIDE\""
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlAssertEquals "package.source_dict.pypi_package_name == \"pello\"" `cat $SOURCE_DICT | jq '.pypi_package_name'` '"pello"'
        rlAssertEquals "package.source_dict.spec_template == \"\"" `cat $SOURCE_DICT | jq '.spec_template'` '""'
        rlAssertEquals "package.source_dict.spec_generator == \"pyp2spec\"" `cat $SOURCE_DICT | jq '.spec_generator'` '"pyp2spec"'

        # PyPI package templates
        rlRun "copr-cli edit-package-pypi $PROJECT --name $PACKAGE_OVERRIDE --template fedora"
        rlRun "copr-cli get-package $PROJECT --name $PACKAGE_OVERRIDE > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.source_dict.spec_template == \"fedora\"" `cat $SOURCE_DICT | jq '.spec_template'` '"fedora"'

        # build the package
        OUTPUT=pello-package.json
        rlRun "copr-cli edit-package-pypi $PROJECT --name $PACKAGE_OVERRIDE --spec-generator pyp2spec"
        rlRun "copr-cli build-package --name $PACKAGE_OVERRIDE $PROJECT -r $CHROOT"
        rlRun "copr-cli get-package $PROJECT --name $PACKAGE_OVERRIDE > $OUTPUT"
        rlAssertEquals "check that pello is used" "$(jq '.source_dict.pypi_package_name' < "$OUTPUT")" '"pello"'

        ## Package listing
        rlAssertEquals "len(package_list) == 4" "$(copr-cli list-packages "$PROJECT" | jq '. | length')" 3

        # try to build copr-cli from pypi, broken now, uncomment once #3517 is fixed
        #rlRun "copr-cli add-package-pypi $PROJECT --name copr-cli --packagename copr-cli"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
