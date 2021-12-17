#! /bin/bash
#
# Copyright (c) 2020 Red Hat, Inc.
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

# shellcheck source=./config
source "$HERE/config"
# shellcheck source=./helpers
source "$HERE/helpers"

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
        workdirSetup
        setupProjectName "bootstrap-project"
    rlPhaseEnd

    rlPhaseStartTest

        rlRun "copr-cli create $PROJECT --bootstrap on --chroot $CHROOT --chroot fedora-rawhide-x86_64 --chroot epel-8-x86_64"

        detail_cmd="curl --silent '$FRONTEND_URL/api_3/project?ownername=$OWNER&projectname=$PROJECTNAME'"
        rlRun "bootstrap=\$($detail_cmd | jq -r '.bootstrap')"
        rlAssertEquals "Check that bootstrap is enabled" "$bootstrap" on

        rlRun "copr-cli edit-chroot $PROJECT/epel-8-x86_64 --bootstrap-image=fedora:$FEDORA_VERSION"
        rlRun "copr-cli edit-chroot $PROJECT/fedora-rawhide-x86_64 --bootstrap=default"
        rlRun -s "copr-cli build $PROJECT $HELLO --nowait"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        chroot=$CHROOT
        rlRun "curl $BACKEND_URL/results/$PROJECT/$chroot/$(printf %08d "$BUILD_ID")-hello/configs.tar.gz | tar xz -O '*configs/child.cfg' > child.cfg"
        rlRun 'grep -F "config_opts['\''use_bootstrap'\''] = True" child.cfg'
        rlRun 'grep -F "config_opts['\''use_bootstrap_image'\''] = False" child.cfg'

        chroot=epel-8-x86_64
        rlRun "curl $BACKEND_URL/results/$PROJECT/$chroot/$(printf %08d "$BUILD_ID")-hello/configs.tar.gz | tar xz -O '*configs/child.cfg' > child.cfg"
        rlRun 'grep -F "config_opts['\''use_bootstrap'\''] = True" child.cfg'
        rlRun 'grep -F "config_opts['\''use_bootstrap_image'\''] = True" child.cfg'
        rlRun 'grep -F "config_opts['\''bootstrap_image'\'']" child.cfg | grep fedora:$FEDORA_VERSION'

        chroot=fedora-rawhide-x86_64
        rlRun "curl $BACKEND_URL/results/$PROJECT/$chroot/$(printf %08d "$BUILD_ID")-hello/configs.tar.gz | tar xz -O '*configs/child.cfg' > child.cfg"
        # neither bootstrap, nor bootstrap image is set
        rlRun "grep use_bootstrap child.cfg" 1

    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
