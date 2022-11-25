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
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        # and install... things
        yum -y install dnf dnf-plugins-core
        TMP=`mktemp -d`
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

        # Test validation output
        OUTPUT=`mktemp`
        rlRun "copr-cli create ${NAME_PREFIX}Project1 --chroot wrong-chroot-name 2> $OUTPUT" 1
        rlRun "cat $OUTPUT |grep -E '^Error: $'"
        case $OWNER in
        @copr) msg_exp="Group copr (fas: gitcopr) already has a project named" ;;
        *) msg_exp="You already have a project named" ;;
        esac
        rlRun "cat $OUTPUT |grep \"\- name: $msg_exp\""
        rlRun "cat $OUTPUT |grep \"\- chroots: 'wrong-chroot-name' is not a valid choice for this field\""

        rlRun "yes | copr-cli new-webhook-secret ${NAME_PREFIX}Project1 | grep -E 'Generated new token: .*-.*-.*-.*-.*'"

        ### ---- BUILDING --------------- ###
        # build - wrong project name
        rlRun "copr-cli build ${NAME_PREFIX}wrong-name http://nowhere/nothing.src.rpm" 1
        # build - wrong chroot name and non-existent url (if url was correct, srpm would be currently built for all available chroots)
        rlRun "copr-cli build -r wrong-chroot-name ${NAME_PREFIX}Project1 http://nowhere/nothing.src.rpm" 1
        # build - OK
        rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO"
        # build - FAIL  (syntax error in source code)
        rlRun "copr-cli build ${NAME_PREFIX}Project1 $EVIL_HELLO" 4
        # check all builds are listed
        OUTPUT=`mktemp`
        rlRun "copr-cli list-builds ${NAME_PREFIX}Project1 > $OUTPUT" 0
        rlAssertEquals "Two builds listed" `cat $OUTPUT | wc -l` 2
        rlAssertEquals "One failed build" `grep -r 'failed' $OUTPUT | wc -l` 1
        rlAssertEquals "One succeeded build" `grep -r 'succeeded' $OUTPUT | wc -l` 1
        # enable Project1 repo
        rlRun "yes | dnf copr enable $DNF_COPR_ID/${NAME_PREFIX}Project1 $CHROOT"
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
        rlRun "yes | dnf copr remove $DNF_COPR_ID/$NAME_PREFIX\"Project1\""
        # disable auto_createrepo
        rlRun "copr-cli modify --disable_createrepo true ${NAME_PREFIX}Project2"
        # build 1st package
        rlRun "copr-cli build ${NAME_PREFIX}Project2 $HELLO"
        # enable Project2 repo
        rlRun "yes | dnf copr enable $DNF_COPR_ID/${NAME_PREFIX}Project2 $CHROOT"
        # try to install - FAIL ( public project metadata not updated)
        rlRun "dnf install -y hello" 1
        # build 2nd package ( requires 1st package for the build)
        rlRun "copr-cli build ${NAME_PREFIX}Project2 https://pagure.io/copr/copr-test-sources/raw/master/f/hello_beaker_test_2-0.0.1-1.src.rpm"
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
        rlRun "yes | dnf copr remove $DNF_COPR_ID/${NAME_PREFIX}Project2"

        ## test build watching and deletion using Project3
        # build 1st package without waiting
        rlRun "copr-cli build --nowait ${NAME_PREFIX}Project3 $HELLO > $TMP/hello_p3.out"
        rlRun "awk '/Created build/ { print \$3 }' $TMP/hello_p3.out > $TMP/hello_p3.id"
        # initial status should be in progress, e.g. pending/running
        rlRun "xargs copr-cli status < $TMP/hello_p3.id | grep -v succeeded"
        # wait for the build to complete and ensure it succeeded
        rlRun "xargs copr-cli watch-build < $TMP/hello_p3.id"
        rlRun "xargs copr-cli status < $TMP/hello_p3.id | grep succeeded"
        # test build deletion
        rlRun "copr-cli status `cat $TMP/hello_p3.id`" 0
        rlRun "cat $TMP/hello_p3.id|xargs copr-cli delete-build"
        rlRun "copr-cli status `cat $TMP/hello_p3.id`" 1

        ## test to modify list of enabled chroots in the project
        # create project
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}ModifyProjectChroots"
        # modify chroots
        rlRun "copr-cli modify --chroot $CHROOT --chroot fedora-rawhide-x86_64 ${NAME_PREFIX}ModifyProjectChroots"
        # the old chroot should not be enabled anymore
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/fedora-23-x86_64" 1
        # only F27 and rawhide from previous modify command should be enabled now
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/$CHROOT" 0
        rlRun "copr-cli get-chroot ${NAME_PREFIX}ModifyProjectChroots/fedora-rawhide-x86_64" 0
        # it should not be possible to select non-existing chroot
        OUTPUT=`mktemp`
        rlRun "copr-cli modify --chroot non-existing-1 ${NAME_PREFIX}ModifyProjectChroots &> $OUTPUT" 1
        rlAssertGrep "'non-existing-1' is not a valid choice for this field" "$OUTPUT"

        ## test distgit builds
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}ProjectDistGitBuilds"
        rlRun "copr-cli buildscm --clone-url https://src.fedoraproject.org/rpms/cpio.git --commit f$FEDORA_VERSION ${NAME_PREFIX}ProjectDistGitBuilds"

        ## test mock-config feature
        mc_project=${NAME_PREFIX}MockConfig
        mc_parent_project=${mc_project}Parent
        mc_output=`mktemp`
        mc_chroot=$CHROOT

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
        rlRun "copr-cli create ${NAME_PREFIX}EditChrootProject --chroot $mc_chroot"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot --upload-comps $TMPCOMPS"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | grep '\"comps_name\": \"$TMPCOMPS_BASENAME\"'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot --delete-comps"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | grep '\"comps_name\": null'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot --repos 'http://foo/repo http://bar/repo' --packages 'gcc'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | jq '.repos == [\"http://foo/repo\", \"http://bar/repo\"]'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | jq '.buildroot_pkgs == [\"gcc\"]'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot --repos '' --packages ''"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | jq '.repos == []'"
        rlRun "copr-cli get-chroot ${NAME_PREFIX}EditChrootProject/$mc_chroot | jq '.buildroot_pkgs == []'"
        rlRun "copr-cli edit-chroot ${NAME_PREFIX}EditChrootProject/fedora-$FEDORA_VERSION-x86_65" 1
        rm $TMPCOMPS

        ## test background builds

        # @FIXME background build tests have never worked reliably, fix it

        # # non-background build should be imported first
        # # the background build should not be listed until non-background builds are imported
        # OUTPUT=`mktemp`
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --background --nowait"
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --nowait > $OUTPUT"
        # rlAssertEquals "Background job should not be listed" `curl $FRONTEND_URL/backend/importing/ |jq 'length'` 1
        # rlAssertEquals "Non-background job should be imported first" \
        #                `curl $FRONTEND_URL/backend/importing/ |jq '.[0].build_id'` \
        #                `tail -n1 $OUTPUT |cut -d' ' -f3`
        #
        # sleep 60
        # # when there are multiple background builds, they should be imported ascendingly by ID
        # OUTPUT=`mktemp`
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --background --nowait > $OUTPUT"
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --background --nowait"
        # rlAssertEquals "Both background builds should be listed" `curl $FRONTEND_URL/backend/importing/ |jq 'length'` 2
        # rlAssertEquals "Build with lesser ID should be imported first" \
        #                `curl $FRONTEND_URL/backend/importing/ |jq '.[0].build_id'` \
        #                `tail -n1 $OUTPUT |cut -d' ' -f3`
        #
        # sleep 60
        # # non-background build should be waiting on the start of the queue
        # OUTPUT=`mktemp`
        # WAITING=`mktemp`
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --background --nowait"
        # rlRun "copr-cli build ${NAME_PREFIX}Project1 $HELLO --nowait > $OUTPUT"
        # # wait until the builds are imported
        # while :; do curl --silent $FRONTEND_URL/backend/pending-jobs/ > $WAITING; if cat $WAITING | grep task_id; then break; fi; done
        # cat $WAITING
        # rlAssertEquals "Non-background build should be waiting on start of the queue" `cat $WAITING |jq '.[0].build_id'` `tail -n1 $OUTPUT |cut -d' ' -f3`


        ## test package creation and editing
        OUTPUT=`mktemp`
        SOURCE_DICT=`mktemp`

        # create special repo for our test
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project4"

        # PyPI package creation
        rlRun "copr-cli add-package-pypi ${NAME_PREFIX}Project4 --name test_package_pypi --packagename pyp2rpm --packageversion 1.5 --pythonversions 3"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_pypi > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.name == \"test_package_pypi\"" `cat $OUTPUT | jq '.name'` '"test_package_pypi"'
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlRun `cat $SOURCE_DICT | jq '.python_versions == ["3"]'` 0 "package.source_dict.python_versions == [\"3\"]"
        rlAssertEquals "package.source_dict.pypi_package_name == \"pyp2rpm\"" `cat $SOURCE_DICT | jq '.pypi_package_name'` '"pyp2rpm"'
        rlAssertEquals "package.source_dict.pypi_package_version == \"bar\"" `cat $SOURCE_DICT | jq '.pypi_package_version'` '"1.5"'

        # PyPI package editing
        rlRun "copr-cli edit-package-pypi ${NAME_PREFIX}Project4 --name test_package_pypi --packagename motionpaint --packageversion 1.4 --pythonversions 3"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_pypi > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.name == \"test_package_pypi\"" `cat $OUTPUT | jq '.name'` '"test_package_pypi"'
        rlAssertEquals "package.source_type == \"pypi\"" `cat $OUTPUT | jq '.source_type'` '"pypi"'
        rlRun `cat $SOURCE_DICT | jq '.python_versions == ["3"]'` 0 "package.source_dict.python_versions == [\"3\"]"
        rlAssertEquals "package.source_dict.pypi_package_name == \"motionpaint\"" `cat $SOURCE_DICT | jq '.pypi_package_name'` '"motionpaint"'
        rlAssertEquals "package.source_dict.pypi_package_version == \"bar\"" `cat $SOURCE_DICT | jq '.pypi_package_version'` '"1.4"'
        rlAssertEquals "package.source_dict.spec_template == \"\"" `cat $SOURCE_DICT | jq '.spec_template'` '""'

        # PyPI package templates
        rlRun "copr-cli edit-package-pypi ${NAME_PREFIX}Project4 --name test_package_pypi --template fedora"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_pypi > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.source_dict.spec_template == \"fedora\"" `cat $SOURCE_DICT | jq '.spec_template'` '"fedora"'

        ## Package listing
        rlAssertEquals "len(package_list) == 1" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 1

        # RubyGems package creation
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name xxx --gem yyy"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name xxx > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.name == \"xxx\"" `cat $OUTPUT | jq '.name'` '"xxx"'
        rlAssertEquals "package.source_type == \"rubygems\"" `cat $OUTPUT | jq '.source_type'` '"rubygems"'
        rlAssertEquals "package.source_dict.gem_name == \"yyy\"" `cat $SOURCE_DICT | jq '.gem_name'` '"yyy"'

        # RubyGems package editing
        rlRun "copr-cli edit-package-rubygems ${NAME_PREFIX}Project4 --name xxx --gem zzz"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name xxx > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.name == \"xxx\"" `cat $OUTPUT | jq '.name'` '"xxx"'
        rlAssertEquals "package.source_type == \"rubygems\"" `cat $OUTPUT | jq '.source_type'` '"rubygems"'
        rlAssertEquals "package.source_dict.gem_name == \"zzz\"" `cat $SOURCE_DICT | jq '.gem_name'` '"zzz"'

        ## Package listing
        rlAssertEquals "len(package_list) == 2" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 2

        ## Package reseting
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}Project4 --name test_package_reset --clone-url $COPR_HELLO_GIT --method tito"

        # before reset
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_reset > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.source_type == \"scm\"" `cat $OUTPUT | jq '.source_type'` '"scm"'
        rlAssertEquals "package.source_dict.clone_url == \"$COPR_HELLO_GIT\"" `cat $SOURCE_DICT | jq '.clone_url'` "\"$COPR_HELLO_GIT\""

        # _do_ reset
        rlRun "copr-cli reset-package ${NAME_PREFIX}Project4 --name test_package_reset"

        # after reset
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_reset > $OUTPUT"
        cat $OUTPUT | jq '.source_dict' > $SOURCE_DICT
        rlAssertEquals "package.source_type == \"unset\"" `cat $OUTPUT | jq '.source_type'` '"unset"'
        rlAssertEquals "package.source_dict == \"{}\"" `cat $OUTPUT | jq '.source_dict'` '{}'

        ## Package listing
        rlAssertEquals "len(package_list) == 3" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 3

        ## Package deletion
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}Project4 --name test_package_delete --clone-url $COPR_HELLO_GIT --method tito"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_delete > /dev/null"

        ## Package listing
        rlAssertEquals "len(package_list) == 4" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 4

        rlRun "copr-cli delete-package ${NAME_PREFIX}Project4 --name test_package_delete"
        rlRun "copr-cli get-package ${NAME_PREFIX}Project4 --name test_package_delete" 1 # package cannot be fetched now (cause it is deleted)

        ## Package listing
        rlAssertEquals "len(package_list) == 3" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 3

        # Packages having all sort of symbols in name, these succeed ..
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name gcc-c++ --gem yyy"
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name python3-ndg_httpsclient --gem yyy"
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name python-boolean.py --gem yyy"

        # .. and these fail.
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name x:x --gem yyy" 1
        rlRun "copr-cli add-package-rubygems ${NAME_PREFIX}Project4 --name x@x --gem yyy" 1

        rlAssertEquals "len(package_list) == 3" `copr-cli list-packages ${NAME_PREFIX}Project4 | jq '. | length'` 6

        ## test package building
        # create special repo for our test
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-rawhide-x86_64 ${NAME_PREFIX}Project6"

        # create a package
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}Project6 --name test_package_scm --clone-url $COPR_HELLO_GIT --method tito"

        # build the package
        rlRun "copr-cli build-package --name test_package_scm ${NAME_PREFIX}Project6 --timeout 10000 -r $CHROOT" # TODO: timeout not honored

        # create pyp2rpm package
        rlRun "copr-cli add-package-pypi ${NAME_PREFIX}Project6 --name test_package_pypi --template fedora --packagename motionpaint --pythonversions 3"

        # build the package
        rlRun "copr-cli build-package --name test_package_pypi ${NAME_PREFIX}Project6 -r $CHROOT"

        # test unlisted_on_hp project attribute
        rlRun "copr-cli create --unlisted-on-hp on --chroot $CHROOT ${NAME_PREFIX}Project7"
        rlRun "curl $FRONTEND_URL --silent | grep Project7" 1 # project won't be present on hp
        rlRun "copr-cli modify --unlisted-on-hp off ${NAME_PREFIX}Project7"
        rlRun "curl $FRONTEND_URL --silent | grep Project7" 0 # project should be visible on hp now

        # test search index update by copr insertion
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-rawhide-x86_64 ${NAME_PREFIX}Project8"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project8 --silent | grep -E \"href=.*${NAME_VAR}Project8.*\"" 1 # search results _not_ returned
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project8 --silent | grep -E \"href=.*${NAME_VAR}Project8.*\"" 0 # search results returned

        # test search index update by package addition
        rlRun "copr-cli create --chroot $CHROOT --chroot fedora-rawhide-x86_64 ${NAME_PREFIX}Project9" && sleep 65
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/"
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project9 --silent | grep -E \"href=.*${NAME_VAR}Project9.*\"" 1 # search results _not_ returned
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}Project9 --name test_package_scm --clone-url $COPR_HELLO_GIT --commit rpkg-util" # insert package to the copr
        rlRun "curl -X POST $FRONTEND_URL/coprs/update_search_index/" # update the index again
        rlRun "curl $FRONTEND_URL/coprs/fulltext/?fulltext=${NAME_VAR}Project9 --silent | grep -E \"href=.*${NAME_VAR}Project9.*\"" 0 # search results are returned now

        # TODO: Modularity integration tests
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project11"
        #rlRun "curl -X POST --user aufnfpybzwwqjtalbial:qmxehlybyghkqlwmyumxuhahbhzxrq --form \"file=@metadata.yaml;filename=module_md\"  http://localhost:8080/api/coprs/${NAME_PREFIX}Project11/modify/$CHROOT/"

        ### ---- FORKING PROJECTS -------- ###
        # default fork usage
        OUTPUT=`mktemp`
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}Project10"
        rlRun "copr-cli build ${NAME_PREFIX}Project10 $HELLO"
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork > $OUTPUT"
        rlAssertEquals "Forking project" `grep -r 'Forking project' $OUTPUT |wc -l` 1
        rlAssertEquals "Info about backend data" `grep -r 'Please be aware that it may take a few minutes to duplicate backend data.' $OUTPUT |wc -l` 1

        # attempt to fork into existing project
        OUTPUT=`mktemp`
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork &> $OUTPUT" 1
        rlAssertEquals "Error existing project" `grep -r '\- You are about to fork into existing project' $OUTPUT |wc -l` 1
        rlAssertEquals "Use --confirm" `grep -r '\- Please use --confirm if you really want to do this' $OUTPUT |wc -l` 1

        # fork into existing project
        OUTPUT=`mktemp`
        rlRun "copr-cli fork ${NAME_PREFIX}Project10 ${NAME_PREFIX}Project10Fork --confirm > $OUTPUT"
        rlAssertEquals "Updating packages" `grep -r 'Updating packages in' $OUTPUT |wc -l` 1

        # give backend some time to fork the data
        echo "sleep 60 seconds to give backend enough time to fork data"
        sleep 60

        # use package from forked project
        rlRun "yes | dnf copr enable $DNF_COPR_ID/${NAME_PREFIX}Project10Fork $CHROOT"
        rlRun "dnf install -y hello"

        # check repo properties
        REPOFILE_BASE=/etc/yum.repos.d/_copr:${FRONTEND_URL//*\/\//}:$(repo_owner):${NAME_VAR}
        REPOFILE=${REPOFILE_BASE}Project10Fork.repo
        rlAssertEquals "Baseurl should point to fork project" `grep -r "^baseurl=" $REPOFILE |grep ${NAME_PREFIX} |wc -l` 1
        rlAssertEquals "GPG pubkey should point to fork project" `grep -r "^gpgkey=" $REPOFILE |grep ${NAME_PREFIX} |wc -l` 1

        # check whether pubkey.gpg exists
        rlRun "curl -f $(grep "^gpgkey=" ${REPOFILE} |sed 's/^gpgkey=//g')"

        rlRun "yes | dnf copr enable $DNF_COPR_ID/${NAME_PREFIX}Project10 $CHROOT"
        REPOFILE_SOURCE=${REPOFILE_BASE}Project10.repo
        rlRun "wget $(grep "^gpgkey=" ${REPOFILE_SOURCE} |sed 's/^gpgkey=//g') -O $TMP/pubkey_source.gpg"
        rlRun "wget $(grep "^gpgkey=" ${REPOFILE} |sed 's/^gpgkey=//g') -O $TMP/pubkey_fork.gpg"
        rlRun "diff $TMP/pubkey_source.gpg $TMP/pubkey_fork.gpg" 1 "simple check that a new key was generated for the forked repo"

        # clean
        rlRun "dnf remove -y hello"
        rlRun "yes | dnf copr remove $DNF_COPR_ID/${NAME_PREFIX}Project10"
        rlRun "yes | dnf copr remove $DNF_COPR_ID/${NAME_PREFIX}Project10Fork"

        # Bug 1365882 - on create group copr, gpg key is generated for user and not for group
        WAITING=`mktemp`
        rlRun "copr-cli create ${NAME_PREFIX}Project12 --chroot $CHROOT" 0
        rlRun "curl --silent $FRONTEND_URL/backend/pending-action/ > $WAITING"
        rlRun "cat $WAITING | grep action_type"
        cat $WAITING # debug
        rlRun "cat $WAITING | grep -E '.*data.*ownername.*' | grep $OWNER" 0

        # Bug 1368181 - delete-project action run just after delete-build action will bring action_dispatcher down
        # FIXME: this test is not a reliable reproducer. Depends on timing as few others.
        # TODO: Remove this.
        rlRun "copr-cli create ${NAME_PREFIX}TestConsequentDeleteActions --chroot $CHROOT" 0
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}TestConsequentDeleteActions --name example --clone-url $COPR_HELLO_GIT --commit rpkg-util"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestConsequentDeleteActions"
        rlAssertEquals "Test that the project was successfully created on backend" `curl -w '%{response_code}' -silent -o /dev/null $BACKEND_URL/results/${NAME_PREFIX}TestConsequentDeleteActions/` 200
        rlRun "python3 <<< \"from copr.v3 import Client; client = Client.create_from_config_file('/root/.config/copr'); client.package_proxy.delete('$OWNER', '${NAME_VAR}TestConsequentDeleteActions', 'example'); client.project_proxy.delete('$OWNER', '${NAME_VAR}TestConsequentDeleteActions')\""
        sleep 30
        rlAssertEquals "Test that the project was successfully deleted from backend" `curl -w '%{response_code}' -silent -o /dev/null $BACKEND_URL/results/${NAME_PREFIX}TestConsequentDeleteActions/` 404

        # test that results and configs are correctly retrieved from builders after build
        rlRun "copr-cli create ${NAME_PREFIX}DownloadMockCfgs --chroot $CHROOT" 0
        rlRun "copr-cli build ${NAME_PREFIX}DownloadMockCfgs $HELLO"
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}DownloadMockCfgs/$CHROOT/
        rlAssertEquals "check that configs.tar.gz exists" "$(find . -name configs.tar.gz | wc -l)" 1
        rlRun "tar tf $(find . -name configs.tar.gz) | grep 'configs/$CHROOT.cfg'" 0
        rlRun "find . -type f | grep 'backend.log'" 0
        rlRun "find . -type f | grep 'root.log'" 0
        cd - && rm -r $MYTMPDIR

        # Bug 1370704 - Internal Server Error (too many values to unpack)
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1370704 --chroot $CHROOT" 0
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}TestBug1370704 --name example --clone-url $COPR_HELLO_GIT --method tito"
        rlRun "copr-cli build-package --name example ${NAME_PREFIX}TestBug1370704"
        # rlAssertEquals "Test OK return code from the monitor API" `curl -w '%{response_code}' -silent -o /dev/null ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1370704/monitor/` 200

        # Bug 1393361 - get_project_details returns incorrect yum_repos
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1393361-1 --chroot $CHROOT" 0
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1393361-2 --chroot $CHROOT" 0
        rlRun "copr-cli buildscm ${NAME_PREFIX}TestBug1393361-2 --clone-url $COPR_HELLO_GIT --method tito" 0
        rlRun "copr-cli buildscm ${NAME_PREFIX}TestBug1393361-1 --clone-url $COPR_HELLO_GIT --commit rpkg-util" 0
        # rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1393361-1/detail/ | grep TestBug1393361-1/$CHROOT" 0
        # rlRun "curl --silent ${FRONTEND_URL}/api/coprs/${NAME_PREFIX}TestBug1393361-2/detail/ | grep TestBug1393361-2/$CHROOT" 0

        # Bug 1444804 - Logs are not present for failed builds
        rlRun "copr-cli create ${NAME_PREFIX}TestBug1444804 --chroot $CHROOT" 0
        copr-cli build ${NAME_PREFIX}TestBug1444804 $EVIL_HELLO
        MYTMPDIR=`mktemp -d -p .` && cd $MYTMPDIR
        wget -r -np $BACKEND_URL/results/${NAME_PREFIX}TestBug1444804/$CHROOT/
        rlAssertEquals "check that configs.tar.gz exists" "$(find . -name configs.tar.gz | wc -l)" 1
        rlRun "tar tf $(find . -name configs.tar.gz) | grep 'configs/$CHROOT.cfg'" 0
        rlRun "find . -type f | grep 'backend.log'" 0
        rlRun "find . -type f | grep 'root.log'" 0
        rlRun "find . -type f | grep 'build.log'" 0
        cd - && rm -r $MYTMPDIR

        ## test building in copr dirs
        rlRun "copr-cli create --chroot $CHROOT ${NAME_PREFIX}CoprDirTest"
        rlRun "copr-cli add-package-scm ${NAME_PREFIX}CoprDirTest --name example --clone-url $COPR_HELLO_GIT --method tito" 0
        rlRun "copr-cli buildscm ${NAME_PREFIX}CoprDirTest:example --clone-url $COPR_HELLO_GIT --method tito" 1
        rlRun "copr-cli buildscm ${NAME_PREFIX}CoprDirTest:custom:example --clone-url $COPR_HELLO_GIT --method tito" 0

        # delete - wrong project name
        rlRun "copr-cli delete ${NAME_PREFIX}wrong-name" 1

        # test building for armhfp
        rlRun "copr-cli create --chroot fedora-36-armhfp ${NAME_PREFIX}ArmhfpBuild"
        rlRun "copr-cli build ${NAME_PREFIX}ArmhfpBuild $HELLO"
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}Project1"
        cleanProject "${NAME_PREFIX}Project2"
        cleanProject "${NAME_PREFIX}Project3"
        cleanProject "${NAME_PREFIX}Project4"
        cleanProject "${NAME_PREFIX}Project6"
        cleanProject "${NAME_PREFIX}Project7"
        cleanProject "${NAME_PREFIX}Project8"
        cleanProject "${NAME_PREFIX}Project9"
        cleanProject "${NAME_PREFIX}Project10"
        cleanProject "${NAME_PREFIX}Project10Fork"
        cleanProject "${NAME_PREFIX}Project11"
        cleanProject "${NAME_PREFIX}Project12"
        cleanProject "${NAME_PREFIX}DownloadMockCfgs"
        cleanProject "${NAME_PREFIX}TestBug1370704"
        cleanProject "${NAME_PREFIX}ProjectDistGitBuilds"
        cleanProject "${NAME_PREFIX}TestBug1393361-1"
        cleanProject "${NAME_PREFIX}TestBug1393361-2"
        cleanProject "${NAME_PREFIX}ModifyProjectChroots"
        cleanProject "${NAME_PREFIX}EditChrootProject"
        cleanProject "${NAME_PREFIX}MockConfig"
        cleanProject "${NAME_PREFIX}MockConfigParent"
        cleanProject "${NAME_PREFIX}TestBug1444804"
        cleanProject "${NAME_PREFIX}CoprDirTest"
        cleanProject "${NAME_PREFIX}ArmhfpBuild"

        # and make sure we haven't left any mess
        rlRun "copr-cli list | grep $NAME_PREFIX" 1

        cleanAction rm -rf "$TMP"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
