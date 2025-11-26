#! /bin/bash
#
# Copyright (c) 2025 Red Hat, Inc.
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


curl()
{
    /usr/bin/curl -o /dev/null -s -f $1
}


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
        workdirSetup
        setupProjectName "WebUI"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        rlRun -s "copr-cli build $PROJECT $HELLO --nowait"
        rlRun parse_build_id
        rlRun "copr watch-build $BUILD_ID"

        owner="${OWNER/@/}"
        project="$NAME_VAR-WebUI"

        # These doesn't prove everything works correctly. We are only checking
        # the status code, nothing else. Also, some of the routes are hidden
        # behind an authentication, so we test the routes very superficially.
        # However, if some of them fails, there is likely a bug.
        rlRun "curl $FRONTEND_URL"
        rlRun "curl $FRONTEND_URL/groups/g/$owner/coprs"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/packages"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/builds"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/monitor"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/monitor/simple"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/monitor/detailed"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/edit"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/permissions"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/integrations"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/repositories"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/delete"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/build/$BUILD_ID"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/package/hello"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/package/hello/rebuild"
        rlRun "curl $FRONTEND_URL/coprs/g/$owner/$project/package/hello/edit"
        rlRun "curl $FRONTEND_URL/api"
        rlRun "curl $FRONTEND_URL/user/info"
        rlRun "curl $FRONTEND_URL/rss"
        rlRun "curl $FRONTEND_URL/status"
        rlRun "curl $FRONTEND_URL/status/importing"
        rlRun "curl $FRONTEND_URL/status/pending"
        rlRun "curl $FRONTEND_URL/status/pending/all"
        rlRun "curl $FRONTEND_URL/status/starting"
        rlRun "curl $FRONTEND_URL/status/running"
        rlRun "curl $FRONTEND_URL/status/batches"
        rlRun "curl $FRONTEND_URL/status/stats"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
