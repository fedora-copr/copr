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
            '(\$a | sort_by(.task_id) | map({task_id: .task_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.task_id) | map({task_id: .task_id, status: (if (.git_hash) then 1 else 0 end)}))'" 0 "Compare expected and actual import outcomes (success/fail)."

        # further tests
        outsize=`jq '. | length' $OUT`
        for (( i = 0; i < $outsize; i++ )); do
            mkdir $MYTMPDIR && cd $MYTMPDIR
            read repo_name git_hash pkg_name task_id <<< `jq ".[$i] | .repo_name, .git_hash, .pkg_name, .task_id" $OUT`
            branch=`echo ${task_id//\"} | cut -d- -f2`
            if [[ git_hash != null ]]; then
                rlRun "git clone http://localhost/cgit/${repo_name}.git" 0
                rlRun "cd $pkg_name" 0
                rlRun "git checkout $git_hash" 0
                rlRun "ls *.spec sources" 0
                rlRun "ls *.src.rpm" 2
                rlRun "fedpkg-copr --dist $branch srpm" 0
                rlRun "ls *.src.rpm" 0
            fi
            cd $TESTPATH && rm -r $MYTMPDIR
        done
    rlPhaseEnd
rlJournalEnd &> /dev/null
