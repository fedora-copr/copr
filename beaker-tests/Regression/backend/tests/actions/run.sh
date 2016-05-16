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

        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.id) | map({id: .id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.id) | map({id: .id, status: .result}))'" 0 "Compare expected and actual action outcomes (success/fail)."

        # further tests
        rlAssertEquals "Test that @actions/copr-to-be-deleted was deleted (and is _not_ accessible now)" `curl -w '%{response_code}' -silent -o /dev/null http://localhost:5002/results/@actions/copr-to-be-deleted/` 404
        rlRun "dnf repoquery --repofrompath=test-createrepo-repo,http://localhost:5002/results/@actions/test-createrepo/chroot-without-repodata/ --disablerepo=* --enablerepo=test-createrepo-repo --refresh --quiet --queryformat '%{reponame}' 2> /dev/null | grep test-createrepo-repo" 0 "Test that @actions/copr-without-repodata/chroot-without-repodata is a valid repomd repository now"
    rlPhaseEnd
rlJournalEnd &> /dev/null
