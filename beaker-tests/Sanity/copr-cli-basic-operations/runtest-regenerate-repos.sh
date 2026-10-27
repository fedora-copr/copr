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

        # Request to regenerate repositories and poll the repository
        # metadata until the action finishes.  We can not sleep for a fixed
        # amount of time here (we used to sleep for 60 seconds) because the
        # single-host Testing Farm machine is heavily loaded --- the backend
        # does a series of Pulp API calls, each of them potentially taking
        # tens of seconds, before the updated metadata are published.
        rlRun "copr-cli regenerate-repos $PROJECT"
        timeout=600
        started=$(date +%s)
        while :; do
            rm -rf /tmp/$PROJECT/2
            lftp -c mirror $URL /tmp/$PROJECT/2 >/dev/null 2>&1
            FILELISTS=`find /tmp/$PROJECT/2/ -name "*-filelists.xml.gz"`
            if [ -n "$FILELISTS" ] && gunzip -c $FILELISTS \
                    | grep -q 'packages="4"'; then
                rlLogInfo "Repository metadata were regenerated"
                break
            fi
            if [ $(( $(date +%s) - started )) -gt "$timeout" ]; then
                rlLogFatal "Repository regeneration is taking too long... stopping."
                break
            fi
            sleep 10
        done

        # Once the repository is regenerated, some packages should be available
        rlRun "gunzip -c $FILELISTS |grep 'packages=\"4\"'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm -rf /tmp/$PROJECT"
        cleanProject "$PROJECT"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
