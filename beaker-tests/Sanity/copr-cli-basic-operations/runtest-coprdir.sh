#! /bin/bash
#
# Copyright (c) 2024 Red Hat, Inc.
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


quick_package_script ()
{
    cp "$HERE/files/quick-package.sh" script
    echo "$1" >> script
}


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        rlAssertRpm "jq"
        setupProjectName "coprdir"
    rlPhaseEnd

    rlPhaseStartTest
        # Test that CoprDirs have their own repositories in the buildroot
        tmp=`mktemp -d`
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"

        # For an ease of implementation, the dependency and the package that
        # requires it are both `hello`. In a real life the first package would
        # be something like `python-copr` or `python-copr-common`, and the
        # second package would be something like `copr-cli` or `copr-backend`.

        # This is the dependency (e.g. python-copr)
        rlRun "curl https://src.fedoraproject.org/rpms/hello/raw/rawhide/f/hello.spec > $tmp/hello-1.spec"
        rlRun "sed -i '1s/^/Epoch: 6\n/' $tmp/hello-1.spec"
        rlRun "copr-cli build $PROJECT:custom:foo $tmp/hello-1.spec"

        # And this is the package that builds on top of it (e.g. copr-cli)
        rlRun "curl https://src.fedoraproject.org/rpms/hello/raw/rawhide/f/hello.spec > $tmp/hello-2.spec"
        rlRun "sed -i '1s/^/BuildRequires: hello >= 6:\n/' $tmp/hello-2.spec"
        rlRun "copr-cli build $PROJECT:custom:foo $tmp/hello-2.spec"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
