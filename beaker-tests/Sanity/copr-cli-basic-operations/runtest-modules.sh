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
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


function wait_for_finished_module()
{
    # Wait until module packages are built or timeout
    # $1 - project name
    # $2 - expected number of packages
    # $3 - temporary file for output
    local project=$1
    local packages=$2
    local tmp=$3
    local timeout=1800
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
        rlAssertEquals "Package $pkg is missing" `cat $tmp |jq '.[] | .name' |grep "$pkg" |wc -l` 1
    done
}


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        yum -y install dnf dnf-plugins-core
        # use the dev instance
        sed -i "s+http://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
        sed -i "s+https://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.4/site-packages/dnf-plugins/copr.py
    rlPhaseEnd

    rlPhaseStartTest
        DATE=$(date +%Y%m%d%H%M%S)
        echo "timestamp=$DATE"

        # Test yaml submit
        PROJECT=module-testmodule-beakertest-$DATE
        copr-cli create $PROJECT --chroot $CHROOT --chroot fedora-rawhide-i386
        yes | cp $HERE/files/testmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/testmodule.yaml
        sed -i "s/\$PLATFORM/$BRANCH/g" /tmp/testmodule.yaml
        rlRun "copr-cli build-module --distgit fedora --yaml /tmp/testmodule.yaml $PROJECT"

        # Test submitting a wrong modulemd
        OUTPUT=`mktemp`
        touch "/tmp/emptyfile.yaml"
        rlRun "copr-cli build-module --distgit fedora --yaml /tmp/emptyfile.yaml $PROJECT &> $OUTPUT" 1
        rlAssertEquals "Module in wrong format" `cat $OUTPUT | grep "Missing modulemd version" |wc -l` 1

        # Test module duplicity
        # @FIXME the request sometimes hangs for some obscure reason
        OUTPUT=`mktemp`
        rlRun "copr-cli build-module --distgit fedora --yaml /tmp/testmodule.yaml $PROJECT &> $OUTPUT" 1
        rlAssertEquals "Module should already exist" `cat $OUTPUT | grep "already exists" |wc -l` 1

        rlAssertEquals "MBS API is no longer available"\
                       `curl -I -s -L $FRONTEND_URL/module/1/module-builds |grep 'HTTP/1.1' |cut -f2 -d ' '` 404

        # Test that module builds succeeded
        PACKAGES=`mktemp`
        wait_for_finished_module "module-testmodule-beakertest-$DATE" 2 $PACKAGES
        test_successful_packages "ed mksh" $PACKAGES

        # Test URL submit
        PROJECT=module-testmoduleurl-beakertest-$DATE
        # meh, the testmodule is hardwired to f35 so we can not simply rely on
        # $CHROOT variable
        rlRun "copr-cli create $PROJECT --chroot $PREV_CHROOT --chroot $CHROOT --chroot fedora-rawhide-i386"
        rlRun "copr-cli build-module --distgit fedora --url https://src.fedoraproject.org/modules/testmodule/raw/fancy/f/testmodule.yaml $PROJECT"
        PACKAGES=`mktemp`
        wait_for_finished_module "module-testmoduleurl-beakertest-$DATE" 1 $PACKAGES
        test_successful_packages "perl-List-Compare" $PACKAGES

        # Test building modulemd in v2 format
        PROJECT=module-testmodulev2-beakertest-$DATE
        # meh, the testmodule is hardwired to f35 so we can not simply rely on
        # $CHROOT variable
        rlRun "copr-cli create $PROJECT --chroot $PREV_CHROOT --chroot $CHROOT --chroot fedora-rawhide-i386"
        # move back to modules/testmodule once this is merged https://src.fedoraproject.org/modules/testmodule/pull-request/1
        rlRun "copr-cli build-module --distgit fedora --url https://src.fedoraproject.org/fork/praiskup/modules/testmodule/raw/fix-rawhide/f/testmodule.yaml $PROJECT"
        PACKAGES=`mktemp`
        wait_for_finished_module "module-testmodulev2-beakertest-$DATE" 3 $PACKAGES
        pkg_list="perl-List-Compare  perl-Tangerine tangerine"
        test_successful_packages "$pkg_list" $PACKAGES

        # @TODO Test that module succeeded
        # We need to implement API for retrieving modules or at least
        # make a reliable way to fetch its state from web UI

        # Test that user-defined macros are in the buildroot
        PROJECT=module-test-macros-module-beakertest-$DATE
        copr-cli create $PROJECT --chroot $CHROOT --chroot fedora-rawhide-i386
        yes | cp $HERE/files/test-macros-module.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/test-macros-module.yaml
        sed -i "s/\$PLATFORM/$BRANCH/g" /tmp/test-macros-module.yaml
        copr-cli build-module --distgit fedora --yaml /tmp/test-macros-module.yaml $PROJECT
        PACKAGES=`mktemp`
        wait_for_finished_module "module-test-macros-module-beakertest-$DATE" 1 $PACKAGES

        SRPM=`rpmbuild -bs $HERE/files/test-macros.spec |grep Wrote: |cut -d ' ' -f2`
        copr-cli build "module-test-macros-module-beakertest-$DATE" $SRPM
        ID=`copr-cli get-package module-test-macros-module-beakertest-$DATE --name test-macros --with-all-builds | jq '.builds[0].id'`
        TMP=`mktemp -d`
        MACROS=`mktemp`
        copr-cli download-build --dest $TMP $ID
        rpm -qp --queryformat '%{DESCRIPTION}' $TMP/$CHROOT/test-macros-1.0-*src.rpm |grep MACRO > $MACROS

        # @FIXME There is a known regression - user macros from modulemd are
        # not used in the buildroot.
        # rlAssertEquals "Both macros should be present" `cat $MACROS |wc -l` 2
        # rlAssertEquals "Macro should correctly expand" `cat $MACROS |grep "This is my module macro" |wc -l` 1
        # rlAssertEquals "Macro using nested macro shoud correctly expand" \
        #                `cat $MACROS |grep "My package is called test-macros" |wc -l` 1

        # Test that it is possible to specify group and project name for the module
        PACKAGES=`mktemp`
        SUFFIX=2
        PROJECT=$OWNER/TestModule$DATE$SUFFIX
        copr-cli create $PROJECT --chroot $CHROOT --chroot fedora-rawhide-i386
        yes | cp $HERE/files/testmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE$SUFFIX/g" /tmp/testmodule.yaml
        sed -i "s/\$PLATFORM/$BRANCH/g" /tmp/testmodule.yaml
        rlRun "copr-cli build-module --distgit fedora --yaml /tmp/testmodule.yaml $PROJECT"
        wait_for_finished_module "$OWNER/TestModule$DATE$SUFFIX" 2 $PACKAGES
        test_successful_packages "ed mksh" $PACKAGES

        # Test that it is possible to build module with package from copr
        PROJECT=module-coprtestmodule-beakertest-$DATE
        copr-cli create $PROJECT --chroot $CHROOT --chroot fedora-rawhide-i386
        yes | cp $HERE/files/coprtestmodule.yaml /tmp
        sed -i "s/\$VERSION/$DATE/g" /tmp/coprtestmodule.yaml
        sed -i "s/\$PLATFORM/$BRANCH/g" /tmp/coprtestmodule.yaml
        sed -i "s/\$OWNER/$USER/g" /tmp/coprtestmodule.yaml
        sed -i "s/\$PROJECT/module-testmodule-beakertest-$DATE/g" /tmp/coprtestmodule.yaml
        sed -i "s|\$DISTGIT_URL|$DISTGIT_URL|g" /tmp/coprtestmodule.yaml
        rlRun "copr-cli build-module --distgit fedora --yaml /tmp/coprtestmodule.yaml $PROJECT"
        PACKAGES=`mktemp`
        wait_for_finished_module "module-coprtestmodule-beakertest-$DATE" 1 $PACKAGES
        test_successful_packages "ed" $PACKAGES

        # @TODO Test that it is possible to build module
        # with few hundreds of packages

        # @TODO Test that there are expected files for built modules on copr-backend


        # Test that module can be enabled with dnf
        # Module repository should be allowed via DNF, but the code isn't merged yet
        # https://github.com/rpm-software-management/dnf-plugins-core/pull/214
        rlRun "curl $FRONTEND_URL/coprs/$USER/module-testmodule-beakertest-$DATE/module_repo/fedora-$FEDORA_VERSION/testmodule-beakertest-$DATE.repo > /etc/yum.repos.d/testmodule.repo"

        rlAssertEquals "Module should be visible in the system" `dnf module list |grep testmodule |grep beakertest |grep -v "Copr modules repo" |wc -l` 1
        rlAssertEquals "Module should be available in the correct version" `dnf module info testmodule:beakertest |grep Version |grep $DATE |wc -l` 1
        rlRun "dnf -y module enable testmodule:beakertest"
        rlRun "dnf -y module install testmodule/default"
        rlRun "rpm -q mksh"
        rlRun "dnf -y module remove testmodule:beakertest/default"
        rlRun "dnf -y module disable testmodule"
        rlRun "rm /etc/yum.repos.d/testmodule.repo"

        # @TODO Test that enabled module info is correct
        # Feature for enabling module from Copr is not in upstream

    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "module-testmodule-beakertest-$DATE"
        cleanProject "module-testmoduleurl-beakertest-$DATE"
        cleanProject "module-test-macros-module-beakertest-$DATE"
        cleanProject "$OWNER/TestModule$DATE$SUFFIX"
        cleanProject "module-coprtestmodule-beakertest-$DATE"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
