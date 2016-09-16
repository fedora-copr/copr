#!/bin/bash

. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export IN=$TESTPATH/action-tasks.json
export OUT=$TESTPATH/action-results.out.json

rlJournalStart
    rlPhaseStartSetup
        dnf -y copr enable @modularity/fm
        dnf -y copr enable @modularity/modulemd
        dnf -y copr enable @modularity/modulemd-resolver
        dnf -y install python3-fm-dnf-plugin
        sed -i 's/enabled\s*=\s*1/enabled=0/' /etc/fm.modules.d/*
        cp _copr_@modularity-template-project.cfg /etc/fm.modules.d/
        dnf -y remove rare_example
        rm -r /var/cache/fm/
        docker exec copr-backend /bin/sh -c 'rm -rf /var/lib/copr/public_html/results/@modularity/template-project/{*+*,modules.json}'
    rlPhaseEnd

    rlPhaseStartTest Actions
        # pre-checks
        rlRun "dnf module list | grep rare_module" 1
        rlRun "rpm -qa | grep rare_example" 1

        # input crunching
        rlRun "/usr/share/copr/mocks/frontend/app.py $TESTPATH $TESTPATH/static" 0

        # basic outcomes test
        rlRun "jq -e -n --argfile a $IN --argfile b $OUT\
            '(\$a | sort_by(.id) | map({id: .id, status: (if (._expected_outcome == \"success\") then 1 else 0 end)})) ==\
            (\$b | sort_by(.id) | map({id: .id, status: .result}))'" 0 "Compare expected and actual action outcomes (success/fail)."

        # post-checks
        rlRun "dnf module list | grep rare_module"
        rlRun "yes | dnf module enable rare_module"
        rlRun "rpm -qa | grep rare_example"
        rlRun "dnf module disable rare_module"
        rlRun "rpm -qa | grep rare_example" 1
    rlPhaseEnd
rlJournalEnd &> /dev/null
