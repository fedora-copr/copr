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
USER=`copr-cli whoami`

echo "FRONTEND_URL = $FRONTEND_URL"
echo "BACKEND_URL = $BACKEND_URL"
echo "USER = $USER"

SCRIPT=`realpath $0`
HERE=`dirname $SCRIPT`

function wait_for_finished_module()
{
    # Wait until module packages are built or timeout
    # $1 - project name
    # $2 - expected number of packages
    # $3 - timeout in seconds
    # $4 - temporary file for output
    local project=$1
    local packages=$2
    local timeout=$3
    local tmp=$4
    local started=$(date +%s)
    while :; do
        now=$(date +%s)
        copr-cli list-packages $project --with-all-builds > $tmp
        if [ `cat $tmp |grep state |grep "succeeded\|failed" |wc -l` -eq $packages ]; then break; fi;
        if [ $(($now - $timeout)) -gt $started ]; then break; fi;
        sleep 10
    done
}


function test_successful_packages()
{
    # Find whether *only* specified packages were successfully built in the project
    # $1 - list of packages, e.g. "foo bar baz"
    # $2 - temporary file with `copr-cli list-packages ...` output of the project
    local packages=$1
    local tmp=$2
    rlAssertEquals "All packages should succeed" `cat $tmp |grep "state" | grep "succeeded" |wc -l` `echo $packages |wc -w`
    for pkg in $packages; do
        rlAssertEquals "Package $pkg is missing" `cat $tmp | grep "name" |grep "$pkg" |wc -l` 1
    done
}


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
        DATE=$(date +%Y%m%d%H%M%S)
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

        # Test that MBS api is not accessible
        rlAssertEquals "MBS API should be directly accessible from copr-frontend only"\
                       `curl -I -s -L $FRONTEND_URL/module/1/module-builds |grep 'HTTP/1.1' |cut -f2 -d ' '` 403

        # Test that module builds succeeded
        PACKAGES=`mktemp`
        wait_for_finished_module "module-testmodule-beakertest-$DATE" 3 600 $PACKAGES
        test_successful_packages "module-build-macros ed mksh" $PACKAGES

        # @TODO Test that module succeeded
        # We need to implement API for retrieving modules or at least
        # make a reliable way to fetch its state from web UI

        # Test that user-defined macros are in the buildroot
        yes | cp $HERE/files/test-macros-module.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/test-macros-module.yaml
        copr-cli build-module --yaml /tmp/test-macros-module.yaml
        PACKAGES=`mktemp`
        wait_for_finished_module "module-test-macros-module-beakertest-$DATE" 2 600 $PACKAGES

        SRPM=`rpmbuild -bs files/test-macros.spec |grep Wrote: |cut -d ' ' -f2`
        copr-cli build "module-test-macros-module-beakertest-$DATE" $SRPM
        ID=`copr-cli get-package module-test-macros-module-beakertest-$DATE --name test-macros --with-all-builds | jq '.builds[0].id'`
        TMP=`mktemp -d`
        MACROS=`mktemp`
        copr-cli download-build --dest $TMP $ID
        rpm -qp --queryformat '%{DESCRIPTION}' $TMP/custom-1-x86_64/test-macros-1.0-*src.rpm |grep MACRO > $MACROS
        rlAssertEquals "Both macros should be present" `cat $MACROS |wc -l` 2
        rlAssertEquals "Macro should correctly expand" `cat $MACROS |grep "This is my module macro" |wc -l` 1
        rlAssertEquals "Macro using nested macro shoud correctly expand" \
                       `cat $MACROS |grep "My package is called test-macros" |wc -l` 1

        # Test that it is possible to specify group and project name for the module
        PACKAGES=`mktemp`
        SUFFIX=2
        yes | cp $HERE/files/testmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE$SUFFIX/g" /tmp/testmodule.yaml
        rlRun "copr-cli build-module --yaml /tmp/testmodule.yaml @copr/TestModule$DATE$SUFFIX"
        wait_for_finished_module "@copr/TestModule$DATE$SUFFIX" 3 600 $PACKAGES
        test_successful_packages "module-build-macros ed mksh" $PACKAGES

        # Test that it is possible to build module with package from copr
        yes | cp $HERE/files/coprtestmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/coprtestmodule.yaml
        sed -i "s/\$OWNER/$USER/g" /tmp/coprtestmodule.yaml
        sed -i "s/\$PROJECT/module-testmodule-beakertest-$DATE/g" /tmp/coprtestmodule.yaml
        rlRun "copr-cli build-module --yaml /tmp/coprtestmodule.yaml"
        PACKAGES=`mktemp`
        wait_for_finished_module "module-coprtestmodule-beakertest-$DATE" 2 600 $PACKAGES
        test_successful_packages "module-build-macros ed" $PACKAGES

        # @TODO Test that it is possible to build module
        # with few hundreds of packages

        # @TODO Test that there are expected files for built modules on copr-backend


        # Test that module can be enabled with dnf
        rlRun "dnf -y upgrade dnf --enablerepo mhatina-dnf-modularity-nightly"

        # Module repository should be allowed via DNF, but the code isn't merged yet
        # https://github.com/rpm-software-management/dnf-plugins-core/pull/214
        rlRun "echo '[$USER-module-testmodule-beakertest-$DATE]' > /etc/yum.repos.d/testmodule.repo"
        rlRun "echo 'name = Copr modules repo for $USER/module-testmodule-beakertest-$DATE' >> /etc/yum.repos.d/testmodule.repo"
        rlRun "echo 'baseurl = $BACKEND_URL/results/$USER/module-testmodule-beakertest-$DATE/modules/custom-1-x86_64+testmodule-beakertest-$DATE/latest/x86_64/' >> /etc/yum.repos.d/testmodule.repo"
        rlRun "echo 'enabled = 1' >> /etc/yum.repos.d/testmodule.repo"

        rlAssertEquals "Module should be visible in the system" `dnf module list |grep testmodule |grep beakertest |grep $DATE |grep -v "Copr modules repo" |wc -l` 1
        rlRun "dnf module enable testmodule:beakertest"
        rlRun "dnf module install testmodule/default"
        rlRun "dnf -y downgrade dnf"


        # @TODO Test that enabled module info is correct
        # Feature for enabling module from Copr is not in upstream

    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
