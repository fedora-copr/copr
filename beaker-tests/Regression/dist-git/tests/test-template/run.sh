#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rlJournalStart
    rlPhaseStartTest TestTemplate
        # write your test here
    rlPhaseEnd
rlJournalEnd &> /dev/null
