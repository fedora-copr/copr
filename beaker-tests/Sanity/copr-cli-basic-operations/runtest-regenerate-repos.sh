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

        if [[ $STORAGE == "pulp" ]]; then
            URL="$PULP_CONTENT_URL/$PROJECT/$CHROOT/repodata/"
        else
            URL="$BACKEND_URL/results/$PROJECT/$CHROOT/repodata/"
        fi

        # Create a project that doesn't generate repositories automatically
        # and build some package in it
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo true $PROJECT"
        rlRun "copr-cli build $PROJECT $HELLO"

        # The repository shouldn't provide any packages
        rlRun "mkdir -p /tmp/$PROJECT/"
        rlRun "lftp -c mirror $URL /tmp/$PROJECT/1"
        FILELISTS=`find /tmp/$PROJECT/1/ -name "*-filelists.xml.gz"`
        rlRun "gunzip -c $FILELISTS |grep 'packages=\"0\"'"

        # Request to regenerate repositories and wait for a minute for the
        # action to finish
        rlRun "copr-cli regenerate-repos $PROJECT"
        sleep 60

        # Once the repository is regenerated, some packages should be available
        rlRun "lftp -c mirror $URL /tmp/$PROJECT/2"
        FILELISTS=`find /tmp/$PROJECT/2/ -name "*-filelists.xml.gz"`
        rlRun "gunzip -c $FILELISTS |grep 'packages=\"4\"'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm -rf /tmp/$PROJECT"
        cleanProject "$PROJECT"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
