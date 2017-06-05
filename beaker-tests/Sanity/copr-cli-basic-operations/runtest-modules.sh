#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest-modules.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: Tests basic operations of copr using copr-cli.
#   Author: Jakub Kadlcik <jkadlcik@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2014 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

if [[ ! $FRONTEND_URL ]]; then
    FRONTEND_URL="http://copr-fe-dev.cloud.fedoraproject.org"
fi
if [[ ! $BACKEND_URL ]]; then
    BACKEND_URL="http://copr-be-dev.cloud.fedoraproject.org"
fi

echo "FRONTEND_URL = $FRONTEND_URL"
echo "BACKEND_URL = $BACKEND_URL"

SCRIPT=`realpath $0`
HERE=`dirname $SCRIPT`

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm "copr-cli"
        rlAssertExists ~/.config/copr
        # testing instance?
        rlAssertGrep "$FRONTEND_URL" ~/.config/copr
        # we don't need to be destroying the production instance
        rlAssertNotGrep "copr.fedoraproject.org" ~/.config/copr
        # token ok? communication ok?
        rlRun "copr-cli list"
        # and install... things
        yum -y install dnf dnf-plugins-core
        # use the dev instance
        sed -i "s+http://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
        sed -i "s+https://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
        dnf -y install jq
    rlPhaseEnd

    rlPhaseStartTest

        # Test yaml submit
        DATE=$(date +%s)
        echo "version=$DATE"
        yes | cp $HERE/files/testmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/testmodule.yaml
        rlRun "copr-cli build-module --yaml /tmp/testmodule.yaml"

        # Test module duplicity
        # @FIXME the request sometimes hangs for some obscure reason
        OUTPUT=`mktemp`
        rlRun "copr-cli build-module --yaml /tmp/testmodule.yaml &> $OUTPUT" 1
        rlAssertEquals "Module should already exist" `cat $OUTPUT | grep "already exists" |wc -l` 1

        # @TODO Test scmurl submit
        # We can't exactly say whether such NSV was built yet so we don't
        # know whether to anticipate a success or an duplicity eror.
        # The whole idea of modules duplicity should be resolved after
        # some time of using the MBS. See a related RFE
        # https://pagure.io/fm-orchestrator/issue/308

        # @TODO Test that MBS api is not accessible
        # Not yet configured

        # Test that module builds succeeded
        PACKAGES=`mktemp`
        STARTED=$(date +%s)

        # Wait until all module packages are built or timeout after 10 minutes
        while :; do
            now=$(date +%s)
            copr-cli list-packages module-testmodule-beakertest-$DATE --with-all-builds > $PACKAGES
            if [ `cat $PACKAGES |grep state |grep "succeeded\|failed" |wc -l` -eq 3 ]; then break; fi;
            if [ $(($now - 600)) -gt $STARTED ]; then break; fi;
            sleep 10
        done

        rlAssertEquals "All packages should succeed" `cat $PACKAGES |grep "state" | grep "succeeded" |wc -l` 3
        for pkg in "module-build-macros" "ed" "mksh"; do
            rlAssertEquals "Package $pkg is missing" `cat $PACKAGES | grep "name" |grep "$pkg" |wc -l` 1
        done

        # @TODO Test that module succeeded
        # We need to implement API for retrieving modules or at least
        # make a reliable way to fetch its state from web UI

        # @TODO Test that it is possible to build module
        # with few hundreds of packages

        # @TODO Test that module can be enabled with dnf
        # We should test this against DNF from
        # https://copr.fedorainfracloud.org/coprs/mhatina/DNF-Modules/
        # Problem is that docker image is F25 and DNF is built only for F26

        # @TODO Test that enabled module info is correct
        # Feature for enabling module from Copr is not in upstream

    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
