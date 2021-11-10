# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

check_repo()
{
    url=$1/repodata/repomd.xml
    rlLog "Checking $url"
    curl --fail "$url" >/dev/null
}

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        PROJECT_F=${NAME_PREFIX}DisableCreaterepoFalse
        PROJECT_T=${NAME_PREFIX}DisableCreaterepoTrue
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo false $PROJECT_F"
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo true $PROJECT_T"
    rlPhaseEnd

    rlPhaseStartTest
        while true; do
            success=:
            for url in \
                $BACKEND_URL/results/$PROJECT_T/$CHROOT/devel \
                $BACKEND_URL/results/$PROJECT_T/$CHROOT \
                $BACKEND_URL/results/$PROJECT_F/$CHROOT ;
            do
                # all those must be created ^^^
                check_repo "$url" && continue
                success=false
                break
            done
            $success && break
            seconds=5
            rlLog "The repositories are not prepared, waiting ${seconds}s more"
            sleep "$seconds"
        done

        rlRun "copr-cli build $PROJECT_F $HELLO"
        rlRun "copr-cli build $PROJECT_T $HELLO"

        rlLog "The devel repo must not exist in $PROJECT_F, till we flip the config"
        rlRun "check_repo $BACKEND_URL/results/$PROJECT_F/$CHROOT/devel" 22


        rlRun "copr-cli modify --disable_createrepo true $PROJECT_F"
        while true; do
            repo=$BACKEND_URL/results/$PROJECT_F/$CHROOT/devel
            check_repo "$repo" && break
            seconds=5
            rlLog "The repo $repo is not prepared yet, waiting ${seconds}s more"
            sleep "$seconds"
        done

    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "$PROJECT_T"
        cleanProject "$PROJECT_F"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
