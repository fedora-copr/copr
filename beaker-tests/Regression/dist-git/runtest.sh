#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Regression/dist-git
#   Description: Tests copr-dist-git features such as importing public or uploaded srpm into dist-git
#   Author: clime <clime@redhat.com>
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2016 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

while [[ $# > 0 ]]
do
key="$1"
case $key in
    --nosetup|-x)
    nosetup=YES
    ;;
    --runonly|-r)
    shift
    runonly=$1
    ;;
    *)
	echo "Unknown option $key."
	exit 1
    ;;
esac
shift
done

# unnecessary on actual beaker machines but good for local docker testing
if ! rpm -qa | grep -E '^rhts.*' &> /dev/null || ! rpm -qa | grep -E '.*beaker.*' &> /dev/null; then
	releasever=`cat /etc/redhat-release | awk '{print $3}'`
	sudo dnf -y --nogpgcheck --repofrompath=beakerrepo,http://beaker-project.org/yum/client/Fedora$releasever/ \
        --enablerepo=beakerrepo install rhts-test-env beakerlib
fi

# include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="copr"

export TESTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

rlJournalStart
    rlPhaseStartSetup
        if [[ ! $nosetup ]]; then
            ./setup.sh
        fi
    rlPhaseEnd

    rlPhaseStartTest Tests
        for t in $TESTPATH/tests/*; do
            if [[ ! $runonly ]] || echo $runonly | grep `basename $t` &> /dev/null; then
                $t/run.sh
            fi
        done
    rlPhaseEnd

    #rlPhaseStartCleanup
    #rlPhaseEnd
rlJournalPrintText
rlJournalEnd
