#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/action-tasks.json
export OUT=$TESTPATH/action-results.out.json

export BUILDTASKSPATH=$TESTPATH/build-tasks

rlJournalStart
    rlPhaseStartTest CancelBuild
        # builds input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $BUILDTASKSPATH $TESTPATH/static &" 0

        # wait until build has been retrieved by backend
        while ! curl --silent http://localhost:5000/backend/pending-jobs/ | grep -E '^\[\]$' ; do
            sleep 1
        done

        sleep 20 # Here backend will attempt to contact us that the job's state changed to 'running'
        kill -9 `pgrep -f app.py` # kill app.py so that it does not wait for build end
        sleep 20 # downloading srpm to builder is taking place, mockchain is not running yet

        # test that the build is running
        rlRun "docker exec copr-backend copr_get_vm_info.py | grep -E '42-fedora-27-x86_64'"

        # action input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # backend will attempt to contact us now before releasing the vm
        rlRun "timeout 30 $TESTPATH/respond_200_to_backend.py" 124

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.id) | map({id: .id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.id) | map({id: .id, status: .result}))'" 0 "Compare expected and actual action outcomes (success/fail)."

        # test that the task has been killed and vm released for another job
        rlRun "docker exec copr-backend copr_get_vm_info.py | grep -E 'task_id: 42-fedora-27-x86_64'" 1
    rlPhaseEnd
rlJournalEnd &> /dev/null
