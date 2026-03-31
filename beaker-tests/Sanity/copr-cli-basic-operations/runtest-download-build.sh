#!/bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


check_downloaded_files()
{
    # When running in Testing Farm, we download a bunch of files like these
    # fedora-43-x86_64/index.html?C=M;O=D
    # fedora-43-x86_64/index.html?C=S;O=D
    # fedora-43-x86_64/index.html?C=M;O=A
    # ...
    # This doesn't happen in production, so let's just remove them
    find . -name 'index.html?*' -delete

    rlAssertEquals "4 .rpm packages are expected" \
        `find $CHROOT -name *.rpm |wc -l` 4

    rlAssertEquals "19 files are expected" \
        `find $CHROOT |wc -l` 19
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        workdirSetup
        setupProjectName "DownloadBuild"
    rlPhaseEnd

    rlPhaseStartTest
        # In Pulp there are two different URLs for the public repository and
        # the devel repository, and the actual RPM files are under those. We
        # want to make sure we can download both published packages and
        # not-yet-published packages.

        rlRun "copr-cli create $PROJECT --chroot $CHROOT --disable_createrepo on"
        rlRun -s "copr-cli build $PROJECT $HELLO --nowait"
        rlRun "parse_build_id"
        rlRun "copr-cli watch-build $BUILD_ID"
        rlRun "copr-cli download-build $BUILD_ID"
        check_downloaded_files

        rlRun "copr-cli modify $PROJECT --disable_createrepo off"
        # Wait until Copr gets a chance to regenerate the public repository
        rlRun "sleep 60"
        rlRun 'rm -rf "$WORKDIR/$CHROOT"'
        rlRun "copr-cli download-build $BUILD_ID"
        check_downloaded_files
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "$PROJECT"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
