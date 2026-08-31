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
PACKAGE_MULTI=copr-rpm-upload-multi-sanity-test

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

# Build a throwaway package with a sub-package (-> multiple binary RPMs) plus
# its srpm, to exercise the multi-file "uploadrpm" scenario (RPM array +
# optional accompanying srpm)
build_local_rpms_with_subpackage_and_srpm()
{
    local workdir
    workdir=$(mktemp -d)
    cat > "$workdir/$PACKAGE_MULTI.spec" <<EOF
Name: $PACKAGE_MULTI
Version: 1
Release: 1
Summary: Throwaway package for the direct RPM upload sanity test
License: MIT
BuildArch: $(rpm --eval '%_arch')

%description
Throwaway package for the direct RPM upload sanity test.

%package subpkg
Summary: Throwaway sub-package for the direct RPM upload sanity test
%description subpkg
Throwaway sub-package for the direct RPM upload sanity test.

%files

%files subpkg
EOF
    rpmbuild -ba "$workdir/$PACKAGE_MULTI.spec" \
        --define "_topdir $workdir" \
        --define "_rpmdir $workdir" \
        --define "_srcrpmdir $workdir" \
        --define "_build_id_links none" >&2
    find "$workdir" -name '*.rpm'
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        setupProjectName "rpm-upload"
    rlPhaseEnd

    rlPhaseStartTest
        if [[ $FRONTEND_URL == "https://copr.stg.fedoraproject.org" ]]; then
            rlLog "Skipping, RPM uploads are not enabled for the Fedora Copr instance"
            exit 0
        fi

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

        # SHA256 checksum verification -- correct checksum should succeed
        rlRun "CHECKSUM=\$(sha256sum $RPM_PATH | cut -d' ' -f1)"
        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT \
            --sha256 $CHECKSUM $PROJECT $RPM_PATH"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        # SHA256 checksum verification -- wrong checksum should be rejected
        rlRun "copr-cli uploadrpm --chroot $CHROOT \
            --sha256 0000000000000000000000000000000000000000000000000000000000000000 \
            $PROJECT $RPM_PATH" 1 "Upload with wrong SHA256 should fail"
    rlPhaseEnd

    rlPhaseStartTest "multi-file uploadrpm: RPM array + --name + --srpm + --logs"
        if [[ $FRONTEND_URL == "https://copr.stg.fedoraproject.org" ]]; then
            rlLog "Skipping, RPM uploads are not enabled for the Fedora Copr instance"
            exit 0
        fi

        rlRun "RPM_PATHS=(\$(build_local_rpms_with_subpackage_and_srpm))" \
            0 "Building local test RPMs (main + sub-package + srpm)"

        SRPM_PATH=
        BINARY_RPMS=()
        for _path in "${RPM_PATHS[@]}"; do
            case "$_path" in
                *.src.rpm) SRPM_PATH=$_path ;;
                *) BINARY_RPMS+=("$_path") ;;
            esac
        done
        rlAssertExists "$SRPM_PATH"
        rlRun "test ${#BINARY_RPMS[@]} -eq 2" 0 \
            "Expecting 2 binary RPMs (main package + sub-package)"

        # a handful of throwaway log/text files to upload alongside the
        # RPMs, covering all four supported extensions
        LOG1=$(mktemp --suffix=.log)
        echo "fake builder-live log" > "$LOG1"
        LOG2=$(mktemp --suffix=.log.gz)
        echo "fake gzipped log" | gzip > "$LOG2"
        LOG3=$(mktemp --suffix=.txt)
        echo "fake notes" > "$LOG3"
        LOG4=$(mktemp --suffix=.txt.gz)
        echo "fake gzipped notes" | gzip > "$LOG4"

        # one SHA256 checksum per binary RPM, in the same order as
        # BINARY_RPMS, to exercise the multi-RPM checksum verification
        CHECKSUMS=()
        for _rpm in "${BINARY_RPMS[@]}"; do
            CHECKSUMS+=("$(sha256sum "$_rpm" | cut -d' ' -f1)")
        done

        # --name is required here since more than one RPM is uploaded and
        # the package name can't be reliably guessed from the filenames
        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT \
            --name $PACKAGE_MULTI \
            --srpm $SRPM_PATH \
            --logs $LOG1 $LOG2 $LOG3 $LOG4 \
            --sha256 ${CHECKSUMS[*]} \
            $PROJECT ${BINARY_RPMS[*]}"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        # verify both the main package and its sub-package are installable
        rlRun "dnf install -y --disablerepo='*' \
            --enablerepo=\"copr:${FRONTEND_PUBLIC_HOST}:$(repo_owner):${PROJECTNAME}\" \
            $PACKAGE_MULTI $PACKAGE_MULTI-subpkg"
        rlAssertRpm "$PACKAGE_MULTI"
        rlAssertRpm "$PACKAGE_MULTI-subpkg"

        # the uploaded logs must be auto-compressed into a single tarball
        # and downloadable the same way as regular build logs (never via
        # Pulp -- they only ever live on the backend filesystem)
        DOWNLOAD_DEST=$(mktemp -d)
        rlRun "copr-cli download-build --dest $DOWNLOAD_DEST --logs $BUILD_ID"
        rlRun "find $DOWNLOAD_DEST -name 'uploaded-logs.tar.gz'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "dnf -y remove $PACKAGE $PACKAGE_MULTI $PACKAGE_MULTI-subpkg"
        rlRun "dnf -y copr remove $DNF_COPR_ID/$PROJECT"
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
