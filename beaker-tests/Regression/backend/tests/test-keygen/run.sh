#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/build-tasks.json
export OUT=$TESTPATH/build-results.out.json

rlJournalStart
    rlPhaseStartTest Builds
        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: .status}))'" 0 "Compare expected and actual build outcomes (success/fail)."

        #rlRun wget http://localhost:5002/results/clime/
    rlPhaseEnd
rlJournalEnd &> /dev/null
