#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/import-tasks.json
export OUT=$TESTPATH/import-results.out.json
export MYTMPDIR=$TESTPATH/tmp # MY- prefix because otherwise there is a conflict with mkstemp

rlJournalStart
    rlPhaseStartTest TestTemplate
        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes comparison
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: (if (.branch_commits) then 1 else 0 end)}))'" 0 "Compare expected and actual import outcomes (success/fail)."

        mkdir $MYTMPDIR && cd $MYTMPDIR
        rlRun "git clone http://localhost/git/clime/example/example.git" 0
        rlRun "cd example" 0
        ls *.spec
        rlAssertEquals "There is only one spec present in master." "`ls *.spec | wc -l`" "1"
        cd $TESTPATH && rm -rf $MYTMPDIR
    rlPhaseEnd
rlJournalEnd &> /dev/null
