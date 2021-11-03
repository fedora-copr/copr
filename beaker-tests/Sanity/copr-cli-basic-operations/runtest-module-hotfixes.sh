#! /bin/bash
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Sanity/auto-prune
#   Description: Tests that --auto-prune works in cli.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2019 Red Hat, Inc.
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
        rlAssertRpm "jq"
    rlPhaseEnd

    rlPhaseStartTest
        # Try to create a project
        rlRun "copr-cli create --module-hotfixes off --chroot $CHROOT ${NAME_PREFIX}ModuleHotfixes"
        rlAssertEquals "" `curl --silent "${FRONTEND_URL}/api_3/project?ownername=${OWNER}&projectname=${NAME_VAR}ModuleHotfixes" |jq ".module_hotfixes"` "false"

        # Try to modify the module_hotfixes value
        rlRun "copr-cli modify --module-hotfixes on ${NAME_PREFIX}ModuleHotfixes"
        rlAssertEquals "" `curl --silent "${FRONTEND_URL}/api_3/project?ownername=${OWNER}&projectname=${NAME_VAR}ModuleHotfixes" |jq ".module_hotfixes"` "true"

        # The module_hotfixes parameter should be set in the repofile
        rlRun "curl --silent ${FRONTEND_URL}/coprs/${NAME_PREFIX}ModuleHotfixes/repo/fedora-${FEDORA_VERSION}/foo.repo |grep module_hotfixes=1"

        # The copr-cli mock-config command should support it
        rlRun "copr mock-config ${NAME_PREFIX}ModuleHotfixes ${CHROOT} |grep module_hotfixes=True"

        # Build task should contain the module_hotfixes field
        rlRun -s "copr-cli build ${NAME_PREFIX}ModuleHotfixes ${HELLO} --nowait"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/backend/get-build-task/${BUILD_ID}-${CHROOT} |jq ".repos[0].module_hotfixes"` "true"

        # When there is a project foo with module_hotfixes set to False, but using a project bar with
        # module_hotfixes set to True as an external repository, the bar should be used with that configuration
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}NotModuleHotfixes"
        rlRun "copr-cli modify ${NAME_PREFIX}NotModuleHotfixes --repo copr://${NAME_PREFIX}ModuleHotfixes"
        rlRun -s "copr-cli build ${NAME_PREFIX}NotModuleHotfixes ${HELLO} --nowait"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/backend/get-build-task/${BUILD_ID}-${CHROOT} |jq ".repos |length"` 2
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/backend/get-build-task/${BUILD_ID}-${CHROOT} |jq '.repos[0] |has("module_hotfixes")'` "false"
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/backend/get-build-task/${BUILD_ID}-${CHROOT} |jq ".repos[1].module_hotfixes"` "true"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}ModuleHotfixes"
        rlRun "copr-cli delete ${NAME_PREFIX}NotModuleHotfixes"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
