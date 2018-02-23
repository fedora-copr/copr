#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export IN=$TESTPATH/build-tasks.json
export OUT=$TESTPATH/build-results.out.json

rlJournalStart
    rlPhaseStartSetup
        docker exec copr-backend /bin/sh -c 'dnf -y install procps-ng'
    rlPhaseEnd

    rlPhaseStartTest DetachedBuilds
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static &" 0

        # wait until build has been retrieved by backend
        while ! curl --silent http://localhost:5000/backend/pending-jobs/ | grep -E '^\[\]$' ; do
            sleep 1
        done

        echo "sleep 8"
        sleep 8 # Here backend will attempt to contact us that the job's state changed to 'running'
        kill -9 `pgrep -f app.py` # kill app.py so that it does not wait for build end
        echo "sleep 8"
        sleep 8 # downloading srpm to builder is taking place, copr-rpmbuild is not running yet

        PID1=`docker exec copr-backend /bin/sh -c 'cat /var/lib/copr-rpmbuild/pid'`
        echo "pid1:" $PID1

        echo "Restart backend"
        docker exec copr-backend /bin/sh -c 'supervisorctl restart all'

        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static &" 0

        # wait until build has been retrieved by backend
        while ! curl --silent http://localhost:5000/backend/pending-jobs/ | grep -E '^\[\]$'  ; do
            sleep 1
        done

        sleep 4 # Here backend will attempt to contact us that the job's state changed to 'running'

        PID2=`docker exec copr-backend /bin/sh -c 'cat /var/lib/copr-rpmbuild/pid'`
        echo "pid2:"$PID2

        rlAssertEquals "Test that copr-rpmbuild has been kept running" $PID1 $PID2

        # wait for the build to be (successfully) finished
        while pgrep -f app.py ; do
            sleep 1
        done

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.build_id) | map({build_id: .build_id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.build_id) | map({build_id: .build_id, status: .status}))'" 0 "Compare expected and actual build outcomes (success/fail)."
    rlPhaseEnd
rlJournalEnd &> /dev/null
