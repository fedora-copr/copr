#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/action-tasks.json
export OUT=$TESTPATH/action-results.out.json

export FRONTEND_URL="http://localhost:5000/"

OWNER="clime"
NAME_VAR="TEST$(date +%s)"
NAME_PREFIX="$OWNER/$NAME_VAR"

rlJournalStart
    rlPhaseStartTest Test
        WAITING=`mktemp`
        rlRun "copr-cli create ${NAME_PREFIX}Project12 --chroot fedora-23-x86_64" 0
        while :; do curl --silent $FRONTEND_URL/backend/waiting/ > $WAITING; if [ `cat $WAITING |wc -l` -gt 4 ]; then break; fi; done
        cat $WAITING # debug
        rlRun "cat $WAITING | grep -E '.*data.*username.*' | grep $OWNER" 0
        rlRun "copr-cli delete ${NAME_PREFIX}Project12"
    rlPhaseEnd
rlJournalEnd &> /dev/null
