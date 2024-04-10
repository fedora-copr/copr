#! /bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

exclusive_arch_package=https://github.com/fedora-copr/copr-test-sources/raw/main/exclusivearch-test-1-1.src.rpm

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
    rlPhaseEnd

    rlPhaseStartTest
        chroots=""
        chroots+=" --chroot fedora-$FEDORA_VERSION-x86_64"
        chroots+=" --chroot fedora-$FEDORA_VERSION-aarch64"
        chroots+=" --chroot fedora-$FEDORA_VERSION-ppc64le"
        chroots+=" --chroot fedora-$FEDORA_VERSION-s390x"

        OUTPUT=`mktemp`

        # Test ExclusiveArch
        rlRun "copr-cli create ${NAME_PREFIX}ExclusiveArch $chroots"
        rlRun "copr-cli build-distgit ${NAME_PREFIX}ExclusiveArch --distgit fedora --name biosdevname --commit $BRANCH"
        rlRun "copr monitor ${NAME_PREFIX}ExclusiveArch > $OUTPUT"
        rlAssertEquals "Skipped chroots" `cat $OUTPUT |grep "skipped" |wc -l` 3
        rlAssertEquals "Succeeded chroots" `cat $OUTPUT |grep "succeeded" |wc -l` 1

        # This is a more complicated package with `BuildArch: noarch` and
        # ExclusiveArch for subpackages. Test that we don't fail while parsing it
        copr_build_and_parse_id build "${NAME_PREFIX}ExclusiveArch" "$exclusive_arch_package"
        json=$(curl "$FRONTEND_URL/api_3/build/built-packages/$BUILD_ID" | jq)
        echo "$json"

        for arch in ppc64le s390x; do
            chroot=fedora-$FEDORA_VERSION-$arch
            output=$(echo "$json" | jq ".\"$chroot\".packages")
            rlAssertEquals "$arch skipped" "$output" "[]"
        done

        for arch in aarch64 x86_64; do
            chroot=fedora-$FEDORA_VERSION-$arch
            output=$(echo "$json" | jq ".\"$chroot\".packages[0].version == \"1\"")
            rlAssertEquals "$arch provides valid Version:" "$output" true
        done

        # Test ExcludeArch
        rlRun "copr-cli create ${NAME_PREFIX}ExcludeArch $chroots"
        rlRun "copr-cli build ${NAME_PREFIX}ExcludeArch files/pkg-with-excludearch.spec "
        rlRun "copr monitor ${NAME_PREFIX}ExcludeArch > $OUTPUT"
        rlAssertEquals "Skipped chroots" `cat $OUTPUT |grep "skipped" |wc -l` 3
        rlAssertEquals "Succeeded chroots" `cat $OUTPUT |grep "succeeded" |wc -l` 1
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanupAction rlRun "copr-cli delete ${NAME_PREFIX}ExclusiveArch"
        cleanupAction rlRun "copr-cli delete ${NAME_PREFIX}ExcludeArch"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
