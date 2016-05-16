#!/bin/bash
# vim: dict+=/usr/share/beakerlib/dictionary.vim cpt=.,w,b,u,t,i,k
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   runtest.sh of /tools/copr/Regression/frontend-api
#   Description: Tests copr-frontend-api features such as importing public or uploaded srpm into frontend
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

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="copr-frontend-api"

rlJournalStart
    rlPhaseStartSetup
        copr_config=~/.config/copr
        username=$(awk -F " = " '/username/ {print $2}' $copr_config)
        login=$(awk -F " = " '/login/ {print $2}' $copr_config)
        token=$(awk -F " = " '/token/ {print $2}' $copr_config)
        copr_url=$(awk -F " = " '/copr_url/ {print $2}' $copr_config)
    rlPhaseEnd

    rlPhaseStartTest
        build_data='
        {
            "project_id": 1,
            "srpm_url": "http://clime.cz/prunerepo-1.1/prunerepo-1.1-1.fc23.src.rpm",
            "chroots": ["fedora-23-x86_64"],
            "enable_net": true
        }'
        curl -X POST -H "Content-Type: application/json" --user $login:$token --data "$build_data" $copr_url/api_2/builds

        #EXAMPLE:
        #curl -X POST --user Y29wcg==##sizmfpcjiqrbddbcjbfq:idcwdnpgjeqvhfejtqmaxtytabyqko --form "name=foobar" http://localhost:8080/api/coprs/clime/test/create_new_package_tito/
    rlPhaseEnd

    rlPhaseStartCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
