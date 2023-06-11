#! /bin/bash

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
        chroots=""
        chroots+=" --chroot fedora-$FEDORA_VERSION-x86_64"
        chroots+=" --chroot fedora-$FEDORA_VERSION-aarch64"
        chroots+=" --chroot fedora-$FEDORA_VERSION-ppc64le"
        chroots+=" --chroot fedora-$FEDORA_VERSION-s390x"

        OUTPUT=`mktemp`

        # Test ExclusiveArch
        rlRun "copr-cli create ${NAME_PREFIX}ExclusiveArch $chroots"
        rlRun "copr-cli build-distgit ${NAME_PREFIX}ExclusiveArch --name biosdevname --commit $BRANCH"
        rlRun "copr monitor ${NAME_PREFIX}ExclusiveArch > $OUTPUT"
        rlAssertEquals "Skipped chroots" `cat $OUTPUT |grep "skipped" |wc -l` 3
        rlAssertEquals "Succeeded chroots" `cat $OUTPUT |grep "succeeded" |wc -l` 1

        # This is a more complicated package with `BuildArch: noarch` and
        # ExclusiveArch for subpackages. Test that we don't fail while parsing it
        rlRun "copr-cli build-distgit ${NAME_PREFIX}ExclusiveArch --name procyon"

        # Test ExcludeArch
        rlRun "copr-cli create ${NAME_PREFIX}ExcludeArch $chroots"
        rlRun "copr-cli build-distgit ${NAME_PREFIX}ExcludeArch --name python-giacpy"
        rlRun "copr monitor ${NAME_PREFIX}ExcludeArch > $OUTPUT"
        rlAssertEquals "Skipped chroots" `cat $OUTPUT |grep "skipped" |wc -l` 3
        rlAssertEquals "Succeeded chroots" `cat $OUTPUT |grep "succeeded" |wc -l` 1
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "copr-cli delete ${NAME_PREFIX}ExclusiveArch"
        rlRun "copr-cli delete ${NAME_PREFIX}ExcludeArch"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
