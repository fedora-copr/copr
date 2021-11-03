# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

rlJournalStart
    rlPhaseStartSetup
        setup_checks
    rlPhaseEnd

    rlPhaseStartTest
        PROJECT=${NAME_PREFIX}RegenerateRepos
        URL="$BACKEND_URL/results/$PROJECT/$CHROOT/repodata/"

        # Create a project that doesn't generate repositories automatically
        # and build some package in it
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo true $PROJECT"
        rlRun "copr-cli build $PROJECT $HELLO"

        # The repository shouldn't provide any packages
        rlRun "wget -r -np -P /tmp/$PROJECT/1 $URL"
        FILELISTS=`find /tmp/$PROJECT/1/ -name "*-filelists.xml.gz"`
        rlRun "gunzip -c $FILELISTS |grep 'packages=\"0\"'"

        # Request to regenerate repositories and wait for a minute for the
        # action to finish
        rlRun "copr-cli regenerate-repos $PROJECT"
        sleep 60

        # Once the repository is regenerated, some packages should be available
        rlRun "wget -r -np -P /tmp/$PROJECT/2 $URL"
        FILELISTS=`find /tmp/$PROJECT/2/ -name "*-filelists.xml.gz"`
        rlRun "gunzip -c $FILELISTS |grep 'packages=\"4\"'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm -rf /tmp/$PROJECT"
        cleanProject "$PROJECT"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
