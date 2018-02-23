#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/build-tasks.json
export OUT=$TESTPATH/build-results.out.json

rlJournalStart
    rlPhaseStartTest RpmSigning
        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: .status}))'" 0 "Compare expected and actual build outcomes (success/fail)."

        tmpdir=`mktemp -d`
        cd $tmpdir
        dnf download --disablerepo=* --repofrompath=examplerepo,http://localhost:5002/results/@copr/copr-dev/fedora-27-x86_64 --enablerepo=examplerepo --refresh example # downloads rpm as well as srpm
        for rpmfile in *; do
            rlRun "rpm -qp --qf '%{RSAHEADER:armor}' $rpmfile 2> /dev/null > $rpmfile.pubkey.gpg" 0 "Test that rpms are signed"
        done

        project_name=`cat $OUT | jq '.[0].project_name' | sed -r 's/"(.*)"/\1/g'`
        project_owner=`cat $OUT | jq '.[0].project_owner' | sed -r 's/"(.*)"/\1/g'`

        # get keyid of the key from pubkey.gpg file for the build task's project_owner and project_name
        rlRun "wget http://localhost:5002/results/$project_owner/$project_name/pubkey.gpg" 0
        cat pubkey.gpg | gpg2 --list-packets | grep keyid: | sed 's/.*keyid: \(.*\)$/\1/' > pubkey.gpg.keyid

        # get keyid of the key that was generated on copr-keygen server for the given project_owner and project_name
        docker exec copr-backend sign -p -u $project_owner#$project_name@copr.fedorahosted.org > signd.pubkey.gpg
        cat signd.pubkey.gpg | gpg2 --list-packets | grep keyid: | sed 's/.*keyid: \(.*\)$/\1/' > signd.pubkey.gpg.keyid

        rlAssertEquals "Check that pubkey.gpg matches the key generated on keygen server" `cat pubkey.gpg.keyid` `cat signd.pubkey.gpg.keyid`

        for rpmfile in *.rpm; do
            cat $rpmfile.pubkey.gpg | gpg2 --list-packets | grep keyid | sed 's/.*keyid \(.*\)$/\1/' > $rpmfile.pubkey.gpg.keyid
            rlAssertEquals "Check that pubkey.gpg matches the key generated on keygen server" `cat $rpmfile.pubkey.gpg.keyid` `cat signd.pubkey.gpg.keyid`
        done
        cd -
        rm -r $tmpdir
    rlPhaseEnd
rlJournalEnd &> /dev/null
