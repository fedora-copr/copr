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
# its srpm, to exercise the multi-RPM tarball upload scenario
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

# Package RPMs/logs/etc. into a single upload tarball with one top-level dir.
# Optional extra args are passed to build_upload_tarball_sha256_json().
build_upload_tarball()
{
    local workdir payload_dir tarball_path file basename
    workdir=$(mktemp -d)
    payload_dir="$workdir/upload"
    mkdir -p "$payload_dir"

    for file in "$@"; do
        basename=$(basename "$file")
        cp "$file" "$payload_dir/$basename"
    done

    if declare -F build_upload_tarball_sha256_json >/dev/null; then
        build_upload_tarball_sha256_json "$payload_dir"
    fi

    tarball_path=$(mktemp --suffix=.tar.gz)
    tar -C "$workdir" -czf "$tarball_path" upload
    rm -rf "$workdir"
    echo "$tarball_path"
}

build_upload_tarball_with_bad_sha256()
{
    local rpm_path="$1"
    local workdir payload_dir tarball_path rpm_name

    workdir=$(mktemp -d)
    payload_dir="$workdir/upload"
    mkdir -p "$payload_dir"
    rpm_name=$(basename "$rpm_path")
    cp "$rpm_path" "$payload_dir/$rpm_name"
    printf '{"%s": "%s"}\n' "$rpm_name" "$(printf '%0*d' 64 0)" \
        > "$payload_dir/sha256.json"

    tarball_path=$(mktemp --suffix=.tar.gz)
    tar -C "$workdir" -czf "$tarball_path" upload
    rm -rf "$workdir"
    echo "$tarball_path"
}

build_upload_tarball_sha256_json()
{
    local payload_dir="$1"
    local file basename checksum
    local -a entries=()

    for file in "$payload_dir"/*; do
        basename=$(basename "$file")
        checksum=$(sha256sum "$file" | cut -d' ' -f1)
        entries+=("\"$basename\": \"$checksum\"")
    done

    printf '{%s}\n' "$(IFS=,; echo "${entries[*]}")" > "$payload_dir/sha256.json"
    cat "$payload_dir/sha256.json"
}

assert_build_chroot_rpms_signed()
{
    local dest="$1"
    local expected_count="$2"
    local chroot_dir="$dest/$CHROOT"
    local pubkey rpmfile verify_out count=0

    pubkey=$(mktemp --suffix=.gpg)
    rlRun "wget -q -O $pubkey $BACKEND_URL/results/$PROJECT/pubkey.gpg" \
        0 "Fetching project pubkey.gpg"
    rlRun "rpmkeys --import $pubkey" 0 "Importing Copr project signing key"
    rm -f "$pubkey"

    rlAssertExists "$chroot_dir"
    while IFS= read -r rpmfile; do
        count=$((count + 1))
        verify_out=$(mktemp)
        rlRun "rpm -Kv '$rpmfile' > '$verify_out' 2>&1" 0 \
            "rpm -Kv $(basename "$rpmfile")"
        rlRun "grep -q 'signature.*: OK' '$verify_out'" 0 \
            "GPG signature OK on $(basename "$rpmfile")"
        rm -f "$verify_out"
    done < <(find "$chroot_dir" -name '*.rpm' | sort)

    rlRun "test $count -ge 1" 0 "At least one RPM in build results"
    if [[ -n "$expected_count" ]]; then
        rlRun "test $count -eq $expected_count" 0 \
            "Expected $expected_count RPM(s) in build results (got $count)"
    fi
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        setupProjectName "rpm-upload"
    rlPhaseEnd

    rlPhaseStartTest "basic uploadrpm tarball"
        if [[ $FRONTEND_URL == "https://copr.stg.fedoraproject.org" ]]; then
            rlLog "Skipping, RPM uploads are not enabled for the Fedora Copr instance"
            exit 0
        fi

        rlRun "copr-cli create --chroot $CHROOT $PROJECT"

        rlRun "RPM_PATH=\$(build_local_rpm)" 0 "Building a local test RPM"
        rlAssertExists "$RPM_PATH"
        rlRun "TARBALL_PATH=\$(build_upload_tarball \"$RPM_PATH\")" \
            0 "Building upload tarball"

        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT \
            --name $PACKAGE --version 1 --release 1 \
            $PROJECT $TARBALL_PATH"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        rlRun "yes | dnf copr enable $DNF_COPR_ID/$PROJECT $CHROOT"
        rlRun "dnf install -y --disablerepo='*' \
            --enablerepo=\"copr:${FRONTEND_PUBLIC_HOST}:$(repo_owner):${PROJECTNAME}\" \
            $PACKAGE"
        rlAssertRpm "$PACKAGE"

        SIGN_CHECK_DEST=$(mktemp -d)
        rlRun "copr-cli download-build $BUILD_ID --dest $SIGN_CHECK_DEST"
        assert_build_chroot_rpms_signed "$SIGN_CHECK_DEST" 1
        rm -rf "$SIGN_CHECK_DEST"
    rlPhaseEnd

    rlPhaseStartTest "uploadrpm tarball with logs"
        if [[ $FRONTEND_URL == "https://copr.stg.fedoraproject.org" ]]; then
            rlLog "Skipping, RPM uploads are not enabled for the Fedora Copr instance"
            exit 0
        fi

        rlRun "RPM_PATH=\$(build_local_rpm)" 0 "Building a local test RPM"
        LOG1=$(mktemp --suffix=.log)
        echo "fake builder-live log" > "$LOG1"
        LOG2=$(mktemp --suffix=.txt)
        echo "fake notes" > "$LOG2"

        rlRun "TARBALL_PATH=\$(build_upload_tarball \"$RPM_PATH\" \"$LOG1\" \"$LOG2\")" \
            0 "Building upload tarball with logs"

        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT \
            --name $PACKAGE --version 1 --release 1 \
            $PROJECT $TARBALL_PATH"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        DOWNLOAD_DEST=$(mktemp -d)
        rlRun "copr-cli download-build --dest $DOWNLOAD_DEST --logs $BUILD_ID"
        rlRun "find $DOWNLOAD_DEST -name 'uploaded-logs.tar.gz'"
    rlPhaseEnd

    rlPhaseStartTest "uploadrpm tarball with bad sha256.json"
        if [[ $FRONTEND_URL == "https://copr.stg.fedoraproject.org" ]]; then
            rlLog "Skipping, RPM uploads are not enabled for the Fedora Copr instance"
            exit 0
        fi

        rlRun "RPM_PATH=\$(build_local_rpm)" 0 "Building a local test RPM"
        rlRun "BAD_TARBALL=\$(build_upload_tarball_with_bad_sha256 \"$RPM_PATH\")" \
            0 "Building upload tarball with bad sha256.json"

        rlRun "copr-cli uploadrpm --chroot $CHROOT \
            --name $PACKAGE --version 1 --release 1 \
            $PROJECT $BAD_TARBALL" 4 \
            "Upload with bad sha256.json should fail on the builder"
    rlPhaseEnd

    rlPhaseStartTest "multi-RPM uploadrpm tarball with srpm and logs"
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

        LOG1=$(mktemp --suffix=.log)
        echo "fake builder-live log" > "$LOG1"

        rlRun "TARBALL_PATH=\$(build_upload_tarball \
            \"${BINARY_RPMS[0]}\" \"${BINARY_RPMS[1]}\" \"$SRPM_PATH\" \"$LOG1\")" \
            0 "Building multi-RPM upload tarball"

        rlRun -s "copr-cli uploadrpm --nowait --chroot $CHROOT \
            --name $PACKAGE_MULTI --version 1 --release 1 \
            $PROJECT $TARBALL_PATH"
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

        rlRun "dnf install -y --refresh --disablerepo='*' \
            --enablerepo=\"copr:${FRONTEND_PUBLIC_HOST}:$(repo_owner):${PROJECTNAME}\" \
            $PACKAGE_MULTI $PACKAGE_MULTI-subpkg"
        rlAssertRpm "$PACKAGE_MULTI"
        rlAssertRpm "$PACKAGE_MULTI-subpkg"

        SIGN_CHECK_DEST=$(mktemp -d)
        rlRun "copr-cli download-build $BUILD_ID --dest $SIGN_CHECK_DEST"
        assert_build_chroot_rpms_signed "$SIGN_CHECK_DEST" 3
        rlRun "find $SIGN_CHECK_DEST/$CHROOT -name '*.src.rpm' | grep -q ." 0 \
            "SRPM present in signed build results"
        rm -rf "$SIGN_CHECK_DEST"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanAction dnf -y remove "$PACKAGE" "$PACKAGE_MULTI" "$PACKAGE_MULTI-subpkg"
        cleanAction dnf -y copr remove "$DNF_COPR_ID/$PROJECT"
        cleanProject
        if ! $COPR_CLEANUP; then
            rlLogInfo "COPR_CLEANUP=false: left project $PROJECT (builds/repos) for inspection"
            rlLogInfo "URL: ${FRONTEND_URL}/coprs/$(repo_owner)/${PROJECTNAME}/"
        fi
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
