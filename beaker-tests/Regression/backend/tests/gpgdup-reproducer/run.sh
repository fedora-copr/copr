. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/build-tasks.json
export OUT=$TESTPATH/build-results.out.json

rlJournalStart
    rlPhaseStartTest GpgDupReproducer
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0
    rlPhaseEnd
rlJournalEnd &> /dev/null
