#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/import-tasks.json
export OUT=$TESTPATH/import-results.out.json
export MYTMPDIR=$TESTPATH/tmp # MY- prefix because otherwise there is a conflict with mkstemp

rlJournalStart
    rlPhaseStartTest Actions
        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes comparison
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: (if (.branch_commits) then 1 else 0 end)}))'" 0 "Compare expected and actual import outcomes (success/fail)."

        # further tests
        outsize=`jq '. | length' $OUT`
        for (( i = 0; i < $outsize; i++ )); do
            mkdir $MYTMPDIR && cd $MYTMPDIR

            git_hash=`jq ".[$i].branch_commits[0] | .git_hash" $OUT`
            repo_name=`jq ".[$i] | .reponame" $OUT`
            pkg_name=`jq ".[$i] | .pkg_name" $OUT`
            task_id=`jq ".[$i] | .build_id" $OUT`

            if [[ git_hash != null ]]; then
                rlLog "-------------- TASK: ${task_id//\"} --------------"
                rlRun "git clone http://localhost/git/${repo_name}.git" 0
                rlRun "cd $pkg_name" 0
                rlRun "git checkout $git_hash" 0
                rlRun "ls *.spec sources" 0
                rlRun "ls *.src.rpm" 2
                rlRun "rpkg srpm --outdir ." 0
                rlRun "ls *.src.rpm" 0
            fi
            cd $TESTPATH && rm -r $MYTMPDIR
        done
    rlPhaseEnd
rlJournalEnd &> /dev/null
