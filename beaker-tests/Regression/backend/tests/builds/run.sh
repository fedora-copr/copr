#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/build-tasks.json
export OUT=$TESTPATH/build-results.out.json

rlJournalStart
    rlPhaseStartSetup
        docker exec copr-backend /bin/mock --scrub=all
    rlPhaseEnd

    rlPhaseStartTest Builds
        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: .status}))'" 0 "Compare expected and actual build outcomes (success/fail)."

        # further tests
        outsize=`jq 'length' $OUT`
        for (( i = 0; i < $outsize; i++ )); do
            results_repo_url=`jq ".[$i] | .results_repo_url" $OUT`
            chroot=`jq ".[$i] | .chroot" $OUT`
            package_name=`jq ".[$i] | .package_name" $OUT`
            build_status=`jq ".[$i] | .status" $OUT`
            if [[ build_status -eq 1 ]]; then
                repo_url=$results_repo_url/$chroot
                rlRun "dnf -y --repofrompath repo,$repo_url --disablerepo=* --enablerepo=repo --quiet --refresh repoquery $package_name" 0
            fi
        done
    rlPhaseEnd
rlJournalEnd &> /dev/null
