#! /bin/bash
#
# Copyright (c) 2026 Red Hat, Inc.
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

. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

PACKAGE=copr-rpm-upload-sanity-test

# Build a throwaway binary RPM locally
build_local_rpm()
{
    local workdir
    workdir=$(mktemp -d)
    cat > "$workdir/$PACKAGE.spec" <<EOF
Name: $PACKAGE
Version: 1
Release: 1
Summary: Throwaway package for the direct RPM upload sanity test
License: MIT
BuildArch: $(rpm --eval '%_arch')

%description
Throwaway package for the direct RPM upload sanity test.

%files
EOF
    rpmbuild -bb "$workdir/$PACKAGE.spec" \
        --define "_topdir $workdir" \
        --define "_rpmdir $workdir" \
        --define "_build_id_links none" >&2
    find "$workdir" -name '*.rpm'
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        setupProjectName "rpm-upload"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"

        rlRun "RPM_PATH=\$(build_local_rpm)" 0 "Building a local test RPM"
        rlAssertExists "$RPM_PATH"

        # go through the real `copr-cli uploadrpm` command, like a real user
        # would -- publishes the RPM directly, skipping the SRPM build and
        # dist-git import phases entirely
        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT $PROJECT $RPM_PATH"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        # verify the uploaded RPM is really installable from the project's repo
        rlRun "yes | dnf copr enable $DNF_COPR_ID/$PROJECT $CHROOT"
        rlRun "dnf install -y --disablerepo='*' \
            --enablerepo=\"copr:${FRONTEND_PUBLIC_HOST}:$(repo_owner):${PROJECTNAME}\" \
            $PACKAGE"
        rlAssertRpm "$PACKAGE"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "dnf -y remove $PACKAGE"
        rlRun "dnf -y copr remove $DNF_COPR_ID/$PROJECT"
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
