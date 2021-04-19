#!/bin/bash

# Include Beaker environment
. /usr/bin/rhts-environment.sh || exit 1
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"


rlJournalStart
    rlPhaseStartSetup
        setup_checks
        RESULTDIR=`mktemp -d`
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli create ${NAME_PREFIX}TestResultsJson --chroot $CHROOT" 0
        rlRun -s "copr-cli build ${NAME_PREFIX}TestResultsJson $HELLO --nowait" 0
        rlRun "parse_build_id"
        rlRun "copr watch-build $BUILD_ID"

	checkResults()
	{
            rlAssertEquals "There should be 4 results" `cat $RESULTDIR/results.json |jq '.packages | length'` 4
	    path=$1
	    rlRun "cat $path |jq -e '.packages[0].name == \"hello-debugsource\"'"
	    rlRun "cat $path |jq -e '.packages[0].epoch == 0'"
	    rlRun "cat $path |jq -e '.packages[0].version == \"2.8\"'"
	    rlRun "cat $path |jq -e '.packages[0].release == \"1.fc$FEDORA_VERSION\"'"
	    rlRun "cat $path |jq -e '.packages[0].arch == \"x86_64\"'"

	    rlRun "cat $path |jq -e '.packages[1].name == \"hello\"'"
	    rlRun "cat $path |jq -e '.packages[1].epoch == 0'"
	    rlRun "cat $path |jq -e '.packages[1].version == \"2.8\"'"
	    rlRun "cat $path |jq -e '.packages[1].release == \"1.fc$FEDORA_VERSION\"'"
	    rlRun "cat $path |jq -e '.packages[1].arch == \"x86_64\"'"

	    rlRun "cat $path |jq -e '.packages[2].name == \"hello\"'"
	    rlRun "cat $path |jq -e '.packages[2].epoch == 0'"
	    rlRun "cat $path |jq -e '.packages[2].version == \"2.8\"'"
	    rlRun "cat $path |jq -e '.packages[2].release == \"1.fc$FEDORA_VERSION\"'"
	    rlRun "cat $path |jq -e '.packages[2].arch == \"src\"'"

	    rlRun "cat $path |jq -e '.packages[3].name == \"hello-debuginfo\"'"
	    rlRun "cat $path |jq -e '.packages[3].epoch == 0'"
	    rlRun "cat $path |jq -e '.packages[3].version == \"2.8\"'"
	    rlRun "cat $path |jq -e '.packages[3].release == \"1.fc$FEDORA_VERSION\"'"
	    rlRun "cat $path |jq -e '.packages[3].arch == \"x86_64\"'"
	}

	# Check the results.json file that is stored on backend
        URL_PATH="results/${NAME_PREFIX}TestResultsJson/$CHROOT/$(build_id_with_leading_zeroes)-hello/results.json"
        rlRun "wget -P $RESULTDIR $BACKEND_URL/$URL_PATH"
	checkResults "$RESULTDIR/results.json"


	# Check the /build-chroot/built-packages/ APIv3 route
        python << END
from copr.v3 import Client
from copr_cli.util import json_dumps

client = Client.create_from_config_file()
response = client.build_chroot_proxy.get_built_packages($BUILD_ID, "$CHROOT")
with open("$RESULTDIR/results-api-build-chroot.json", "w") as f:
    f.write(json_dumps(response))
END
	checkResults "$RESULTDIR/results-api-build-chroot.json"


	# Check the /build/built-packages/ APIv3 route
        python << END
from copr.v3 import Client
from copr_cli.util import json_dumps

client = Client.create_from_config_file()
response = client.build_proxy.get_built_packages($BUILD_ID)
with open("$RESULTDIR/results-api-build.json", "w") as f:
    f.write(json_dumps(response["$CHROOT"]))
END
	checkResults "$RESULTDIR/results-api-build.json"


    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "${NAME_PREFIX}TestResultsJson"
        rlRun "rm -rf $RESULTDIR/*"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
