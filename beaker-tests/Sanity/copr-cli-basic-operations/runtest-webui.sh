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
    /usr/bin/curl -A "$COPR_USER_AGENT" -o /dev/null -s -f "$@"
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

        owner_part=$OWNER
        case $OWNER in
        @*)
            owner_part=g/${OWNER/@/}
            rlRun "curl $FRONTEND_URL/groups/$owner_part/coprs"
            ;;
        esac

        # These doesn't prove everything works correctly. We are only checking
        # the status code, nothing else. Also, some of the routes are hidden
        # behind an authentication, so we test the routes very superficially.
        # However, if some of them fails, there is likely a bug.
        rlRun "curl $FRONTEND_URL/coprs/"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/packages"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/builds"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/monitor"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/monitor/simple"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/monitor/detailed"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/edit"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/permissions"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/integrations"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/repositories"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/delete"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/build/$BUILD_ID"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/package/hello"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/package/hello/rebuild"
        rlRun "curl $FRONTEND_URL/coprs/$owner_part/$PROJECTNAME/package/hello/edit"
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
