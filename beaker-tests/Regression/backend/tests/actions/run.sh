#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/action-tasks.json
export OUT=$TESTPATH/action-results.out.json

rlJournalStart
    rlPhaseStartTest Actions
        # pre-checks
        rlAssertEquals "Test that @actions/copr-to-be-deleted is accessible through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/copr-to-be-deleted/` 200
        rlRun "dnf repoquery --repofrompath=test-createrepo-repo,http://localhost:5002/results/@actions/test-createrepo/chroot-without-repodata/ --disablerepo=* --enablerepo=test-createrepo-repo --refresh --quiet --queryformat '%{reponame}' 2> /dev/null | grep test-createrepo-repo" 1 "Test that @actions/copr-without-repodata/chroot-without-repodata is not a valid repomd repository"
        rlAssertEquals "Test that @actions/test-rename is accessible through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-rename/` 200
        rlAssertEquals "Test that @actions/test-rename-renamed is not accessible through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-rename-renamed/` 404
        rlRun "docker exec copr-backend sign -p -u @actions#test-gen-pubkey@copr.fedorahosted.org" 1 "Test that there is no key for @actions/test-gen-pubkey project"
        rlAssertEquals "Test that there is no comps.xml file for @actions/test-save-comps/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-comps/fedora-27-x86_64/comps.xml` 404
        rlAssertEquals "Test that there is no module_md.yaml file for @actions/test-save-module_md/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-module_md/fedora-27-x86_64/module_md.yaml` 404
        rlAssertEquals "Test that there is comps.xml file present for @actions/test-delete-comps/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-delete-comps/fedora-27-x86_64/comps.xml` 200
        rlAssertEquals "Test that there is module_md.yaml file present for @actions/test-delete-module_md/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-delete-module_md/fedora-27-x86_64/module_md.yaml` 200
        rlAssertEquals "Test that there is no comps.xml file for @actions/test-save-comps-no-chroot/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-comps-no-chroot/fedora-27-x86_64/comps.xml` 404
        rlAssertEquals "Test that there is no module_md.yaml file for @actions/test-save-module_md-no-chroot/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-module_md-no-chroot/fedora-27-x86_64/module_md.yaml` 404

        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.id) | map({id: .id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.id) | map({id: .id, status: .result}))'" 0 "Compare expected and actual action outcomes (success/fail)."

        # further tests
        rlAssertEquals "Test that @actions/copr-to-be-deleted was deleted (and is _not_ accessible now)" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/copr-to-be-deleted/` 404
        rlRun "dnf repoquery --repofrompath=test-createrepo-repo,http://localhost:5002/results/@actions/test-createrepo/chroot-without-repodata/ --disablerepo=* --enablerepo=test-createrepo-repo --refresh --quiet --queryformat '%{reponame}' 2> /dev/null | grep test-createrepo-repo" 0 "Test that @actions/copr-without-repodata/chroot-without-repodata is a valid repomd repository now"
        rlAssertEquals "Test that @actions/test-rename is not accessible through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-rename/` 404
        rlAssertEquals "Test that @actions/test-rename-renamed is accessible through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-rename-renamed/` 200
        rlRun "docker exec copr-backend sign -p -u @actions#test-gen-pubkey@copr.fedorahosted.org" 0 "Test that the key for @actions/test-gen-pubkey project has been generated"
        rlAssertEquals "Test that there is comps.xml file present for @actions/test-save-comps/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-comps/fedora-27-x86_64/comps.xml` 200
        rlAssertEquals "Test that there is module_md.yaml file present for @actions/test-save-module_md/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-module_md/fedora-27-x86_64/module_md.yaml` 200
        rlAssertEquals "Test that there is no comps.xml file present for @actions/test-delete-comps/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-delete-comps/fedora-27-x86_64/comps.xml` 404
        rlAssertEquals "Test that there is no module_md.yaml file present for @actions/test-delete-module_md/fedora-27-x86_64" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-delete-module_md/fedora-27-x86_64/module_md.yaml` 404
        rlAssertEquals "Test that there exists comps.xml file for @actions/test-save-comps-no-chroot/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-comps-no-chroot/fedora-27-x86_64/comps.xml` 200
        rlAssertEquals "Test that there exists module_md.yaml file for @actions/test-save-module_md-no-chroot/fedora-27-x86_64 through http" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/test-save-module_md-no-chroot/fedora-27-x86_64/module_md.yaml` 200
        rlAssertEquals "Test that pubkey is created in fork" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/foo/barFork/pubkey.gpg` 200
        rlAssertEquals "Test that build RPM file was forked" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/foo/barFork/fedora-23-x86_64/00000064-rare_example/rare_example-1.0.3-2.fc23.x86_64.rpm` 200
        rlRun "dnf repoquery --repofrompath=test-createrepo-repo,http://localhost:5002/results/foo/barFork/fedora-23-x86_64/ --disablerepo=* --enablerepo=test-createrepo-repo --refresh --quiet --queryformat '%{reponame}' 2> /dev/null | grep test-createrepo-repo" 0 "Test that fork project has valid repomd repository"
    rlPhaseEnd
rlJournalEnd &> /dev/null
