#!/bin/bash
# vim: dict=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Sanity/copr-cli-basic-operations
#   Description: Tests basic operations of copr using copr-cli.
#   Author: Adam Samalik <asamalik@redhat.com>
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

PACKAGE="copr"
OWNER="@copr"
NAME_VAR="TEST$(date +%s)" # names should be unique
NAME_PREFIX="$OWNER/$NAME_VAR"
if [[ ! $FRONTEND_URL ]]; then
    FRONTEND_URL="http://copr-fe-dev.cloud.fedoraproject.org"
fi
if [[ ! $BACKEND_URL ]]; then
    BACKEND_URL="http://copr-be-dev.cloud.fedoraproject.org"
fi

echo "FRONTEND_URL = $FRONTEND_URL"
echo "BACKEND_URL = $BACKEND_URL"

# Some tests might want to install built packages
# Therefore, these packages need to be built for the same fedora version
# as this script is going to be run from
CHROOT="fedora-27-x86_64"

SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

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
        /usr/lib/python3.6/site-packages/dnf-plugins/copr.py
        sed -i "s+https://copr.fedoraproject.org+$FRONTEND_URL+g" \
        /usr/lib/python3.6/site-packages/dnf-plugins/copr.py
        dnf -y install jq
    rlPhaseEnd

    rlPhaseStartTest
        ### ---- CREATING PROJECTS ------ ###
        # create - OK
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project1"
        # create - the same name again
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project1" 1
        # create - wrong chroot name
        rlRun "copr-cli create --chroot wrong-chroot-name ${NAME_PREFIX}Project2" 1
        # create second project
        rlRun "copr-cli create --chroot $CHROOT --repo 'copr://${NAME_PREFIX}Project1' ${NAME_PREFIX}Project2"
        # create third project
        rlRun "copr-cli create --chroot $CHROOT --repo 'copr://${NAME_PREFIX}Project1' ${NAME_PREFIX}Project3"
        ### left after this section: Project1, Project2, Project3

        ### ---- BUILDING --------------- ###
        # build - wrong project name
        rlRun "copr-cli build ${NAME_PREFIX}wrong-name http://nowhere/nothing.src.rpm" 1
        # build - wrong chroot name and non-existent url (if url was correct, srpm would be currently built for all available chroots)
        rlRun "copr-cli build -r wrong-chroot-name ${NAME_PREFIX}Project1 http://nowhere/nothing.src.rpm" 4
        # build - OK
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        # build - the same version modified - SKIPPED
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/changed/hello-2.8-1.fc20.src.rpm"
        # build - FAIL  (syntax error in source code)
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/evilhello-2.8-1.fc20.src.rpm" 4
        # enable Project1 repo
        rlRun "yes | dnf copr enable ${NAME_PREFIX}Project1 $CHROOT"
        # install hello package
        rlRun "dnf install -y hello"
        # and check whether it's installed
        rlAssertRpm "hello"
        # run it
        rlRun "hello"
        # check if we have the first package and not the skipped one
        rlRun "hello | grep changed" 1
        ### left after this section: Project1, hello installed

        ## test auto_createrepo property of copr-project using Project2
        # remove hello
        rlRun "dnf remove hello -y"
        # disable Project1 repo
        rlRun "yes | dnf copr disable $NAME_PREFIX\"Project1\""
        # disable auto_createrepo
        rlRun "copr-cli modify --disable_createrepo true ${NAME_PREFIX}Project2"
        # build 1st package
        rlRun "copr-cli build ${NAME_PREFIX}Project2 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        # enable Project2 repo
        rlRun "yes | dnf copr enable ${NAME_PREFIX}Project2 $CHROOT"
        # try to install - FAIL ( public project metadata not updated)
        rlRun "dnf install -y hello" 1
        # build 2nd package ( requires 1st package for the build)
        rlRun "copr-cli build ${NAME_PREFIX}Project2 https://frostyx.fedorapeople.org/hello_beaker_test_2-0.0.1-1.fc22.src.rpm"
        # try to install - FAIL ( public project metadata not updated)
        rlRun "dnf install -y hello_beaker_test_2" 1
        # re-enabling metadata generation
        rlRun "copr-cli modify --disable_createrepo false ${NAME_PREFIX}Project2"
        # waiting for action to complete
        sleep 120
        # trying to install
        rlRun "dnf install -y --refresh hello_beaker_test_2"
        # clean
        rlRun "dnf remove -y hello_beaker_test_2"

        ## test build watching and deletion using Project3
        # build 1st package without waiting
        rlRun "copr-cli build --nowait ${NAME_PREFIX}Project3 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm > hello_p3.out"
        rlRun "awk '/Created build/ { print \$3 }' hello_p3.out > hello_p3.id"
        # initial status should be in progress, e.g. pending/running
        rlRun "xargs copr-cli status < hello_p3.id | grep -v succeeded"
        # wait for the build to complete and ensure it succeeded
        rlRun "xargs copr-cli watch-build < hello_p3.id"
        rlRun "xargs copr-cli status < hello_p3.id | grep succeeded"
        # test build deletion
        rlRun "copr-cli status `cat hello_p3.id`" 0
        rlRun "cat hello_p3.id|xargs copr-cli delete-build"
        rlRun "copr-cli status `cat hello_p3.id`" 1

        ## test --auto-prune option
        rlRun "copr-cli create --auto-prune off --chroot fedora-27-x86_64 ${NAME_PREFIX}AutoPrune"
        rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}AutoPrune/detail/ | grep '\"auto_prune\": false'" 0
        rlRun "copr-cli modify --auto-prune on ${NAME_PREFIX}AutoPrune"
        rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}AutoPrune/detail/ | grep '\"auto_prune\": true'" 0

        ## test to modify list of enabled chroots in the project
        # create project
        rlRun "copr-cli create --chroot fedora-26-x86_64 ${NAME_PREFIX}ModifyProjectChroots"
        # modify chroots
        rlRun "copr-cli modify --chroot fedora-27-x86_64 --chroot fedora-rawhide-x86_64 ${NAME_PREFIX}ModifyProjectChroots"
        # the old chroot should not be enabled anymore
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/fedora-26-x86_64" 1
        # only F26 and rawhide from previous modify command should be enabled now
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/fedora-27-x86_64" 0
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/fedora-rawhide-x86_64" 0
        # it should not be possible to select non-existing chroot
        OUTPUT=`mktemp`
        rlRun "copr-cli modify --chroot non-existing-1 ${NAME_PREFIX}ModifyProjectChroots &> $OUTPUT" 1
        rlAssertEquals "It is not possible to enable non-existing chroot " `cat $OUTPUT |grep "Such chroot is not enabled: non-existing-1" |wc -l` 1

        ## test distgit builds
        rlRun "copr-cli create --chroot fedora-26-x86_64 ${NAME_PREFIX}ProjectDistGitBuilds"
        rlRun "copr-cli buildfedpkg --clone-url https://src.fedoraproject.org/rpms/389-admin-console.git --branch f26 ${NAME_PREFIX}ProjectDistGitBuilds"

        ## test mock-config feature
        mc_project=${NAME_PREFIX}MockConfig
        mc_parent_project=${mc_project}Parent
        mc_output=`mktemp`
        mc_chroot=fedora-27-x86_64

        rlRun "copr-cli create --chroot $mc_chroot $mc_parent_project"
        create_opts="--repo copr://$mc_parent_project"
        rlRun "copr-cli create --chroot $mc_chroot $create_opts $mc_project"
        rlRun "copr-cli mock-config $mc_project $mc_chroot > $mc_output"
        rlRun "grep results/$mc_parent_project $mc_output"
        # Non-existent project/chroot.
        rlRun "copr-cli mock-config notexistent/notexistent $mc_chroot" 1
        rlRun "copr-cli mock-config $mc_project fedora-14-x86_64" 1

        ## test edit chroot
        TMPCOMPS=`mktemp`
        echo "
        0 NFS File Server {
          @ Network Server
          nfs-utils
        }
        " > $TMPCOMPS
        TMPCOMPS_BASENAME=`basename $TMPCOMPS`
        rlRun "copr-cli create ${NAME_PREFIX}EditChrootProject --chroot fedora-27-x86_64"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 --upload-comps $TMPCOMPS"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"comps_name\": \"$TMPCOMPS_BASENAME\"'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 --delete-comps"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"comps_name\": null'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 --repos 'http://foo/repo http://bar/repo' --packages 'gcc'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"repos\": \"http://foo/repo http://bar/repo\"'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"buildroot_pkgs\": \"gcc\"'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 --repos '' --packages ''"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"repos\": \"\"'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_64 | grep '\"buildroot_pkgs\": \"\"'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-27-x86_65" 1
        rm $TMPCOMPS

        ## test background builds

        # non-background build should be imported first
        # the background build should not be listed until non-background builds are imported
        OUTPUT=`mktemp`
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --background --nowait"
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --nowait > $OUTPUT"
        rlAssertEquals "Background job should not be listed" `curl $FRONTEND_URL/backend/importing/ |jq 'length'` 1
        rlAssertEquals "Non-background job should be imported first" \
                       `curl $FRONTEND_URL/backend/importing/ |jq '.[0].build_id'` \
                       `tail -n1 $OUTPUT |cut -d' ' -f3`

        sleep 60
        # when there are multiple background builds, they should be imported ascendingly by ID
        OUTPUT=`mktemp`
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --background --nowait > $OUTPUT"
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --background --nowait"
        rlAssertEquals "Both background builds should be listed" `curl $FRONTEND_URL/backend/importing/ |jq 'length'` 2
        rlAssertEquals "Build with lesser ID should be imported first" \
                       `curl $FRONTEND_URL/backend/importing/ |jq '.[0].build_id'` \
                       `tail -n1 $OUTPUT |cut -d' ' -f3`

        sleep 60
        # non-background build should be waiting on the start of the queue
        OUTPUT=`mktemp`
        WAITING=`mktemp`
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --background --nowait"
        rlRun "copr-cli build ${NAME_PREFIX}Project1 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm --nowait > $OUTPUT"
        # wait until the builds are imported
        while :; do curl --silent $FRONTEND_URL/backend/pending-jobs/ > $WAITING; if cat $WAITING | grep task_id; then break; fi; done
        cat $WAITING
        rlAssertEquals "Non-background build should be waiting on start of the queue" `cat $WAITING |jq '.[0].build_id'` `tail -n1 $OUTPUT |cut -d' ' -f3`


        ## test package creation and editing
        OUTPUT=`mktemp`
        SOURCE_JSON=`mktemp`

        # create special repo for our test
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project4"

        # invalid package data
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project4 --name test_package_tito --git-url invalid_url" 1

        # Tito package creation
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project4 --name test_package_tito --git-url http://github.com/clime/example.git --test on --webhook-rebuild on --git-branch foo --git-dir bar"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_tito > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_tito\"" `cat $OUTPUT | jq '.name'` '"test_package_tito"'
        rlAssertEquals "package.webhook_rebuild == \"true\"" `cat $OUTPUT | jq '.webhook_rebuild'` 'true'
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_json.srpm_build_method == \"tito_test"\" `cat $SOURCE_JSON | jq '.srpm_build_method'` '"tito_test"'
        rlAssertEquals "package.source_json.clone_url == \"http://github.com/clime/example.git\"" `cat $SOURCE_JSON | jq '.clone_url'` '"http://github.com/clime/example.git"'
        rlAssertEquals "package.source_json.committish == \"foo\"" `cat $SOURCE_JSON | jq '.committish'` '"foo"'
        rlAssertEquals "package.source_json.subdirectory == \"bar\"" `cat $SOURCE_JSON | jq '.subdirectory'` '"bar"'

        # Tito package editing
        rlRun "copr-cli edit-package-tito ${NAME_PREFIX}Project4 --name test_package_tito --git-url http://github.com/clime/example2.git --test off --webhook-rebuild off --git-branch bar --git-dir foo"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_tito > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_tito\"" `cat $OUTPUT | jq '.name'` '"test_package_tito"'
        rlAssertEquals "package.webhook_rebuild == \"false\"" `cat $OUTPUT | jq '.webhook_rebuild'` 'false'
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_json.srpm_build_method == \"tito\"" `cat $SOURCE_JSON | jq '.srpm_build_method'` '"tito"'
        rlAssertEquals "package.source_json.clone_url == \"http://github.com/clime/example2.git\"" `cat $SOURCE_JSON | jq '.clone_url'` '"http://github.com/clime/example2.git"'
        rlAssertEquals "package.source_json.committish == \"bar\"" `cat $SOURCE_JSON | jq '.committish'` '"bar"'
        rlAssertEquals "package.source_json.subdirectory == \"foo\"" `cat $SOURCE_JSON | jq '.subdirectory'` '"foo"'

        ## Package listing
        rlAssertEquals "len(package_list) == 1" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 1

        # PyPI package creation
        rlRun "copr-cli add-package-pypi ${NAME_PREFIX}Project4 --name test_package_pypi --packagename pyp2rpm --packageversion 1.5 --pythonversions 3 2"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_pypi > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_pypi\"" `cat $OUTPUT | jq '.name'` '"test_package_pypi"'
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlRun `cat $SOURCE_JSON | jq '.python_versions == ["3", "2"]'` 0 "package.source_json.python_versions == [\"3\", \"2\"]"
        rlAssertEquals "package.source_json.pypi_package_name == \"pyp2rpm\"" `cat $SOURCE_JSON | jq '.pypi_package_name'` '"pyp2rpm"'
        rlAssertEquals "package.source_json.pypi_package_version == \"bar\"" `cat $SOURCE_JSON | jq '.pypi_package_version'` '"1.5"'

        # PyPI package editing
        rlRun "copr-cli edit-package-pypi ${NAME_PREFIX}Project4 --name test_package_pypi --packagename motionpaint --packageversion 1.4 --pythonversions 2 3"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_pypi > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_pypi\"" `cat $OUTPUT | jq '.name'` '"test_package_pypi"'
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlRun `cat $SOURCE_JSON | jq '.python_versions == ["2", "3"]'` 0 "package.source_json.python_versions == [\"2\", \"3\"]"
        rlAssertEquals "package.source_json.pypi_package_name == \"motionpaint\"" `cat $SOURCE_JSON | jq '.pypi_package_name'` '"motionpaint"'
        rlAssertEquals "package.source_json.pypi_package_version == \"bar\"" `cat $SOURCE_JSON | jq '.pypi_package_version'` '"1.4"'

        ## Package listing
        rlAssertEquals "len(package_list) == 2" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 2

        # MockSCM package creation
        rlRun "copr-cli add-package-mockscm ${NAME_PREFIX}Project4 --name test_package_mockscm --scm-type git --scm-url http://github.com/clime/example.git --scm-branch foo --spec example.spec"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_mockscm > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_mockscm\"" `cat $OUTPUT | jq '.name'` '"test_package_mockscm"'
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_json.type == \"git\"" `cat $SOURCE_JSON | jq '.type'` '"git"'
        rlAssertEquals "package.source_json.clone_url == \"http://github.com/clime/example.git\"" `cat $SOURCE_JSON | jq '.clone_url'` '"http://github.com/clime/example.git"'
        rlAssertEquals "package.source_json.committish == \"foo\"" `cat $SOURCE_JSON | jq '.committish'` '"foo"'
        rlAssertEquals "package.source_json.spec == \"example.spec\"" `cat $SOURCE_JSON | jq '.spec'` '"example.spec"'
        rlAssertEquals "package.source_json.srpm_build_method == \"rpkg\"" `cat $SOURCE_JSON | jq '.srpm_build_method'` '"rpkg"'

        # MockSCM package editing
        rlRun "copr-cli edit-package-mockscm ${NAME_PREFIX}Project4 --name test_package_mockscm --scm-type svn --scm-url http://github.com/clime/example2.git --scm-branch bar --spec example2.spec"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_mockscm > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"test_package_mockscm\"" `cat $OUTPUT | jq '.name'` '"test_package_mockscm"'
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_json.type == \"svn\"" `cat $SOURCE_JSON | jq '.type'` '"svn"'
        rlAssertEquals "package.source_json.clone_url == \"http://github.com/clime/example2.git\"" `cat $SOURCE_JSON | jq '.clone_url'` '"http://github.com/clime/example2.git"'
        rlAssertEquals "package.source_json.committish == \"bar\"" `cat $SOURCE_JSON | jq '.committish'` '"bar"'
        rlAssertEquals "package.source_json.spec == \"example2.spec\"" `cat $SOURCE_JSON | jq '.spec'` '"example2.spec"'
        rlAssertEquals "package.source_json.srpm_build_method == \"rpkg\"" `cat $SOURCE_JSON | jq '.srpm_build_method'` '"rpkg"'

        ## Package listing
        rlAssertEquals "len(package_list) == 3" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 3

        # RubyGems package creation
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name xxx --gem yyy"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name xxx > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"xxx\"" `cat $OUTPUT | jq '.name'` '"xxx"'
        rlAssertEquals "package.source_type == \"rubygems\"" `cat $OUTPUT | jq '.source_type'` '"rubygems"'
        rlAssertEquals "package.source_json.gem_name == \"yyy\"" `cat $SOURCE_JSON | jq '.gem_name'` '"yyy"'

        # RubyGems package editing
        rlRun "copr-cli edit-package-rubygems ${NAME_PREFIX}Project4 --name xxx --gem zzz"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name xxx > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.name == \"xxx\"" `cat $OUTPUT | jq '.name'` '"xxx"'
        rlAssertEquals "package.source_type == \"rubygems\"" `cat $OUTPUT | jq '.source_type'` '"rubygems"'
        rlAssertEquals "package.source_json.gem_name == \"zzz\"" `cat $SOURCE_JSON | jq '.gem_name'` '"zzz"'

        ## Package listing
        rlAssertEquals "len(package_list) == 4" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 4

        ## Package reseting
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project4 --name test_package_reset --git-url http://github.com/clime/example.git"

        # before reset
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_reset > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_json.clone_url == \"http://github.com/clime/example.git\"" `cat $SOURCE_JSON | jq '.clone_url'` '"http://github.com/clime/example.git"'

        # _do_ reset
        rlRun "copr-cli reset-package ${NAME_PREFIX}Project4 --name test_package_reset"

        # after reset
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_reset > $OUTPUT"
        cat $OUTPUT | jq '.source_json' | sed -r 's/"(.*)"/\1/g' | sed -r 's/\\(.)/\1/g' > $SOURCE_JSON
        rlAssertEquals "package.source_type == \"unset\"" `cat $OUTPUT | jq '.source_type'` '"unset"'
        rlAssertEquals "package.source_json == \"{}\"" `cat $OUTPUT | jq '.source_json'` '"{}"'

        ## Package listing
        rlAssertEquals "len(package_list) == 5" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 5

        ## Package deletion
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project4 --name test_package_delete --git-url http://github.com/clime/example.git"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_delete > /dev/null"

        ## Package listing
        rlAssertEquals "len(package_list) == 6" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 6

        rlRun "copr-cli delete-package ${NAME_PREFIX}Project4 --name test_package_delete"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_delete" 1 # package cannot be fetched now (cause it is deleted)

        ## Package listing
        rlAssertEquals "len(package_list) == 5" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 5

        ## Test package listing attributes
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project5"
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project5 --name example --git-url http://github.com/clime/example.git"

        BUILDS=`mktemp`
        LATEST_BUILD=`mktemp`
        LATEST_SUCCEEDED_BUILD=`mktemp`

        # run the tests before build
        rlRun "copr-cli get-package ${NAME_PREFIX}Project5 --name example --with-all-builds --with-latest-build --with-latest-succeeded-build > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Builds are empty" `cat $BUILDS` '[]'
        rlAssertEquals "There is no latest build." `cat $LATEST_BUILD` 'null'
        rlAssertEquals "And there is no latest succeeded build." `cat $LATEST_SUCCEEDED_BUILD` 'null'

        # run the build and wait
        rlRun "copr-cli buildtito --git-url http://github.com/clime/example.git ${NAME_PREFIX}Project5 | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > succeeded_example_build_id"

        # this build should fail
        rlRun "copr-cli buildtito --git-url http://github.com/clime/example.git --git-branch noluck --test on ${NAME_PREFIX}Project5 | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > failed_example_build_id"

        # run the tests after build
        rlRun "copr-cli get-package ${NAME_PREFIX}Project5 --name example --with-all-builds --with-latest-build --with-latest-succeeded-build > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Build list contain two builds" `cat $BUILDS | jq '. | length'` 2
        rlAssertEquals "The latest build is the failed one." `cat $LATEST_BUILD | jq '.id'` `cat failed_example_build_id`
        rlAssertEquals "The latest succeeded build is also correctly returned." `cat $LATEST_SUCCEEDED_BUILD | jq '.id'` `cat succeeded_example_build_id`

        # run the same tests for list-packages cmd and its first (should be the only one) result
        rlRun "copr-cli list-packages ${NAME_PREFIX}Project5 --with-all-builds --with-latest-build --with-latest-succeeded-build | jq '.[0]' > $OUTPUT"
        cat $OUTPUT | jq '.builds' > $BUILDS
        cat $OUTPUT | jq '.latest_build' > $LATEST_BUILD
        cat $OUTPUT | jq '.latest_succeeded_build' > $LATEST_SUCCEEDED_BUILD

        rlAssertEquals "Build list contain two builds" `cat $BUILDS | jq '. | length'` 2
        rlAssertEquals "The latest build is the failed one." `cat $LATEST_BUILD | jq '.id'` `cat failed_example_build_id`
        rlAssertEquals "The latest succeeded build is also correctly returned." `cat $LATEST_SUCCEEDED_BUILD | jq '.id'` `cat succeeded_example_build_id`

        ## test package building
        # create special repo for our test
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-27-x86_64 ${NAME_PREFIX}Project6"

        # create tito package
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project6 --name test_package_tito --git-url http://github.com/clime/example.git --test on"

        # build the package
        rlRun "copr-cli build-package --name test_package_tito ${NAME_PREFIX}Project6 --timeout 10000 -r $CHROOT" # TODO: timeout not honored

        # test disable_createrepo
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo false ${NAME_PREFIX}DisableCreaterepoFalse"
        rlRun "copr-cli build ${NAME_PREFIX}DisableCreaterepoFalse http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        rlRun "curl --silent $BACKEND_URL/results/${NAME_PREFIX}DisableCreaterepoFalse/$CHROOT/devel/repodata/ | grep \"404.*Not Found\"" 0

        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo true ${NAME_PREFIX}DisableCreaterepoTrue"
        rlRun "copr-cli build ${NAME_PREFIX}DisableCreaterepoTrue http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        rlRun "curl --silent $BACKEND_URL/results/${NAME_PREFIX}DisableCreaterepoTrue/$CHROOT/devel/repodata/ | grep -E \"404.*Not Found\"" 1

        # test unlisted_on_hp project attribute
        rlRun "copr-cli create --unlisted-on-hp on --chroot $CHROOT ${NAME_PREFIX}Project7"
        rlRun "curl $FRONTEND_URL --silent | grep Project7" 1 # project won't be present on hp
        rlRun "copr-cli modify --unlisted-on-hp off ${NAME_PREFIX}Project7"
        rlRun "curl $FRONTEND_URL --silent | grep Project7" 0 # project should be visible on hp now

        # test search index update by copr insertion
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-27-x86_64 ${NAME_PREFIX}Project8"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project8 --silent | grep -E \"href=.*${NAME_VAR}Project8.*\"" 1 # search results _not_ returned
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project8 --silent | grep -E \"href=.*${NAME_VAR}Project8.*\"" 0 # search results returned

        # test search index update by package addition
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-27-x86_64 ${NAME_PREFIX}Project9" && sleep 65
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project9 --silent | grep -E \"href=.*${NAME_VAR}Project9.*\"" 1 # search results _not_ returned
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}Project9 --name test_package_tito --git-url http://github.com/clime/example.git --test on" # insert package to the copr
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/" # update the index again
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project9 --silent | grep -E \"href=.*${NAME_VAR}Project9.*\"" 0 # search results are returned now

        # TODO: Modularity integration tests
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project11"
        #rlRun "curl -X POST --user aufnfpybzwwqjtalbial:qmxehlybyghkqlwmyumxuhahbhzxrq --form \"file=@metadata.yaml;filename=module_md\"  http://localhost:8080/api/coprs/${NAME_PREFIX}Project11/modify/$CHROOT/"

        ### ---- FORKING PROJECTS -------- ###
        # default fork usage
        OUTPUT=`mktemp`
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project10"
        rlRun "copr-cli build ${NAME_PREFIX}Project10 http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork > $OUTPUT"
        rlAssertEquals "Forking project" `grep -r 'Forking project' $OUTPUT |wc -l` 1
        rlAssertEquals "Info about backend data" `grep -r 'Please be aware that it may take a few minutes to duplicate backend data.' $OUTPUT |wc -l` 1

        # attempt to fork into existing project
        OUTPUT=`mktemp`
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork &> $OUTPUT" 1
        rlAssertEquals "Error existing project" `grep -r 'Error: You are about to fork into existing project' $OUTPUT |wc -l` 1
        rlAssertEquals "Use --confirm" `grep -r 'Please use --confirm if you really want to do this' $OUTPUT |wc -l` 1

        # fork into existing project
        OUTPUT=`mktemp`
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork --confirm > $OUTPUT"
        rlAssertEquals "Updating packages" `grep -r 'Updating packages in' $OUTPUT |wc -l` 1

        # give backend some time to fork the data
        echo "sleep 60 seconds to give backend enough time to fork data"
        sleep 60

        # use package from forked project
        rlRun "yes | dnf copr enable ${NAME_PREFIX}Project10Fork $CHROOT"
        rlRun "dnf install -y hello"

        # check repo properties
        REPOFILE=$(echo /etc/yum.repos.d/_copr_${NAME_PREFIX}Project10Fork.repo |sed 's/\/TEST/-TEST/g')
        rlAssertEquals "Baseurl should point to fork project" `grep -r "^baseurl=" $REPOFILE |grep ${NAME_PREFIX} |wc -l` 1
        rlAssertEquals "GPG pubkey should point to fork project" `grep -r "^gpgkey=" $REPOFILE |grep ${NAME_PREFIX} |wc -l` 1

        # check whether pubkey.gpg exists
        rlRun "curl -f $(grep "^gpgkey=" ${REPOFILE} |sed 's/^gpgkey=//g')"

        rlRun "yes | dnf copr enable ${NAME_PREFIX}Project10 $CHROOT"
        REPOFILE_SOURCE=$(echo /etc/yum.repos.d/_copr_${NAME_PREFIX}Project10.repo |sed 's/\/TEST/-TEST/g')
        rlRun "wget $(grep "^gpgkey=" ${REPOFILE_SOURCE} |sed 's/^gpgkey=//g') -O pubkey_source.gpg"
        rlRun "wget $(grep "^gpgkey=" ${REPOFILE} |sed 's/^gpgkey=//g') -O pubkey_fork.gpg"
        rlRun "diff pubkey_source.gpg pubkey_fork.gpg" 1 "simple check that a new key was generated for the forked repo"

        # clean
        rlRun "dnf remove -y hello"
        rlRun "yes | dnf copr disable  ${NAME_PREFIX}Project10Fork"

        # Bug 1365882 - on create group copr, gpg key is generated for user and not for group
        WAITING=`mktemp`
        rlRun "copr-cli create ${NAME_PREFIX}Project12 --chroot $CHROOT" 0
        while :; do curl --silent $FRONTEND_URL/backend/pending-action/ > $WAITING; if cat $WAITING | grep task_id; then break; fi; done
        cat $WAITING # debug
        rlRun "cat $WAITING | grep -E '.*data.*username.*' | grep $OWNER" 0

        # Bug 1368181 - delete-project action run just after delete-build action will bring action_dispatcher down
        # FIXME: this test is not a reliable reproducer. Depends on timing as few others.
        # TODO: Remove this.
        rlRun "copr-cli create ${NAME_PREFIX}TestConsequentDeleteActions --chroot $CHROOT" 0
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}TestConsequentDeleteActions --name example --git-url http://github.com/clime/example.git"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestConsequentDeleteActions"
        rlAssertEquals "Test that the project was successfully created on backend" `curl -w '%{response_code}' -silent -o /dev/null $BACKEND_URL/results/${NAME_PREFIX}TestConsequentDeleteActions/` 200
        rlRun "python <<< \"from copr.client import CoprClient; client = CoprClient.create_from_file_config('/root/.config/copr'); client.delete_package('${NAME_VAR}TestConsequentDeleteActions', 'example', '$OWNER'); client.delete_project('${NAME_VAR}TestConsequentDeleteActions', '$OWNER')\""
        sleep 11 # default sleeptime + 1
        rlAssertEquals "Test that the project was successfully deleted from backend" `curl -w '%{response_code}' -silent -o /dev/null $BACKEND_URL/results/${NAME_PREFIX}TestConsequentDeleteActions/` 404

        # Bug 1368259 - Deleting a build from a group project doesn't delete backend files
        rlRun "copr-cli create ${NAME_PREFIX}TestDeleteGroupBuild --chroot $CHROOT" 0
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}TestDeleteGroupBuild --name example --git-url http://github.com/clime/example.git"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestDeleteGroupBuild | grep 'Created builds:' | sed 's/Created builds: \([0-9][0-9]*\)/\1/g' > TestDeleteGroupBuild_example_build_id.txt"
        BUILD_ID=`cat TestDeleteGroupBuild_example_build_id.txt`
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}TestDeleteGroupBuild/$CHROOT/
        rlRun "find . -type d | grep '${BUILD_ID}-example'" 0 "Test that the build directory (ideally with results) is present on backend"
        cd - && rm -r $MYTMPDIR
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        rlRun "copr-cli delete-package --name example ${NAME_PREFIX}TestDeleteGroupBuild" # FIXME: We don't have copr-cli delete-build yet
        sleep 11 # default sleeptime + 1
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}TestDeleteGroupBuild/$CHROOT/
        rlRun "find . -type d | grep '${BUILD_ID}-example'" 1 "Test that the build directory is not present on backend"
        cd - && rm -r $MYTMPDIR

        # test that results and configs are correctly retrieved from builders after build
        rlRun "copr-cli create ${NAME_PREFIX}DownloadMockCfgs --chroot $CHROOT" 0
        rlRun "copr-cli build ${NAME_PREFIX}DownloadMockCfgs http://asamalik.fedorapeople.org/hello-2.8-1.fc20.src.rpm"
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}DownloadMockCfgs/$CHROOT/
        rlRun "find . -type f | grep 'configs/$CHROOT.cfg'" 0
        rlRun "find . -type f | grep 'backend.log'" 0
        rlRun "find . -type f | grep 'root.log'" 0
        cd - && rm -r $MYTMPDIR

        # Bug 1370704 - Internal Server Error (too many values to unpack)
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1370704 --chroot $CHROOT" 0
        rlRun "copr-cli add-package-tito ${NAME_PREFIX}TestBug1370704 --name example --git-url http://github.com/clime/example.git"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestBug1370704"
        rlAssertEquals "Test OK return code from the monitor API" `curl -w '%{response_code}' -silent -o /dev/null ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1370704/monitor/` 200

        # Bug 1393361 - get_project_details returns incorrect yum_repos
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1393361-1 --chroot fedora-27-x86_64" 0
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1393361-2 --chroot fedora-27-x86_64" 0
        rlRun "copr-cli buildtito ${NAME_PREFIX}TestBug1393361-2 --git-url https://github.com/clime/example.git" 0
        rlRun "copr-cli buildtito ${NAME_PREFIX}TestBug1393361-1 --git-url https://github.com/clime/example.git" 0
        rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1393361-1/detail/ | grep TestBug1393361-1/fedora-27-x86_64" 0
        rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1393361-2/detail/ | grep TestBug1393361-2/fedora-27-x86_64" 0

        # Bug 1444804 - Logs are not present for failed builds
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1444804 --chroot $CHROOT" 0
        copr-cli build ${NAME_PREFIX}TestBug1444804 http://asamalik.fedorapeople.org/evilhello-2.8-1.fc20.src.rpm
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}TestBug1444804/$CHROOT/
        rlRun "find . -type f | grep 'configs/$CHROOT.cfg'" 0
        rlRun "find . -type f | grep 'backend.log'" 0
        rlRun "find . -type f | grep 'root.log'" 0
        rlRun "find . -type f | grep 'build.log'" 0
        cd - && rm -r $MYTMPDIR

        # test use_bootstrap_container setting
        rlRun "copr-cli create ${NAME_PREFIX}BootstrapProject --use-bootstrap on --chroot $CHROOT"
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}BootstrapProject/detail/ |jq '.detail.use_bootstrap_container'` true
        rlRun "copr-cli modify ${NAME_PREFIX}BootstrapProject --use-bootstrap off"
        rlAssertEquals "" `curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}BootstrapProject/detail/ |jq '.detail.use_bootstrap_container'` false


        ### ---- DELETING PROJECTS ------- ###
        # delete - wrong project name
        rlRun "copr-cli delete ${NAME_PREFIX}wrong-name" 1
        # delete the projects
        rlRun "copr-cli delete ${NAME_PREFIX}Project1"
        rlRun "copr-cli delete ${NAME_PREFIX}Project2"
        rlRun "copr-cli delete ${NAME_PREFIX}Project3"
        rlRun "copr-cli delete ${NAME_PREFIX}Project4"
        rlRun "copr-cli delete ${NAME_PREFIX}Project5"
        rlRun "copr-cli delete ${NAME_PREFIX}Project6"
        rlRun "copr-cli delete ${NAME_PREFIX}DisableCreaterepoFalse"
        rlRun "copr-cli delete ${NAME_PREFIX}DisableCreaterepoTrue"
        rlRun "copr-cli delete ${NAME_PREFIX}Project7"
        rlRun "copr-cli delete ${NAME_PREFIX}Project8"
        rlRun "copr-cli delete ${NAME_PREFIX}Project9"
        rlRun "copr-cli delete ${NAME_PREFIX}Project10"
        rlRun "copr-cli delete ${NAME_PREFIX}Project10Fork"
        rlRun "copr-cli delete ${NAME_PREFIX}Project11"
        rlRun "copr-cli delete ${NAME_PREFIX}Project12"
        rlRun "copr-cli delete ${NAME_PREFIX}DownloadMockCfgs"
        rlRun "copr-cli delete ${NAME_PREFIX}TestBug1370704"
        rlRun "copr-cli delete ${NAME_PREFIX}ProjectDistGitBuilds"
        rlRun "copr-cli delete ${NAME_PREFIX}TestBug1393361-1"
        rlRun "copr-cli delete ${NAME_PREFIX}TestBug1393361-2"
        rlRun "copr-cli delete ${NAME_PREFIX}AutoPrune"
        rlRun "copr-cli delete ${NAME_PREFIX}ModifyProjectChroots"
        rlRun "copr-cli delete ${NAME_PREFIX}EditChrootProject"
        rlRun "copr-cli delete ${NAME_PREFIX}TestDeleteGroupBuild"
        rlRun "copr-cli delete ${NAME_PREFIX}MockConfig"
        rlRun "copr-cli delete ${NAME_PREFIX}MockConfigParent"
        rlRun "copr-cli delete ${NAME_PREFIX}TestBug1444804"
        rlRun "copr-cli delete ${NAME_PREFIX}BootstrapProject"
        # and make sure we haven't left any mess
        rlRun "copr-cli list | grep $NAME_PREFIX" 1
        ### left after this section: hello installed
    rlPhaseEnd

    rlPhaseStartCleanup
        rm $SCRIPTPATH/TestDeleteGroupBuild_example_build_id.txt
        rm $SCRIPTPATH/failed_example_build_id
        rm $SCRIPTPATH/hello_p3.id
        rm $SCRIPTPATH/hello_p3.out
        rm $SCRIPTPATH/pubkey_fork.gpg
        rm $SCRIPTPATH/pubkey_source.gpg
        rm $SCRIPTPATH/succeeded_example_build_id
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
