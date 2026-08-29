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
    # fedora-44-x86_64/index.html?C=M;O=D
    # fedora-44-x86_64/index.html?C=S;O=D
    # fedora-44-x86_64/index.html?C=M;O=A
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
        rlRun 'rm -rf "$WORKDIR/$CHROOT"'

        spec_url=https://src.fedoraproject.org/rpms/hello/raw/f44/f/hello.spec
        rlRun "curl $spec_url > $tmp/hello.spec"
        rlRun "sed -i '1s/^/Epoch: 6\n/' $tmp/hello.spec"
        rlRun -s "copr-cli build $PROJECT $tmp/hello.spec --nowait"
        rlRun "parse_build_id"
        rlRun "copr-cli watch-build $BUILD_ID"
        python << END
from copr.v3 import Client
from pathlib import Path
from urllib.request import urlretrieve
client = Client.create_from_config_file()
urls = client.build_chroot_proxy.get_results_urls($BUILD_ID, "$CHROOT")
destdir = Path("$WORKDIR/$CHROOT")
destdir.mkdir(parents=True, exist_ok=True)
for url in urls:
    print(f"Downloading: {url}")
    name = url.split("/")[-1]
    urlretrieve(url, destdir / name)
END
        rlAssertEquals "4 .rpm packages are expected" \
            `find $CHROOT -name '*.rpm' |wc -l` 4

    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "$PROJECT"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
