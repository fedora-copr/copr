# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        PROJECT_F=${NAME_PREFIX}DisableCreaterepoFalse
        PROJECT_T=${NAME_PREFIX}DisableCreaterepoTrue
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo false $PROJECT_F"
        rlRun "copr-cli create --chroot $CHROOT --disable_createrepo true $PROJECT_T"
    rlPhaseEnd

    rlPhaseStartTest
        rlRun "copr-cli build $PROJECT_F $HELLO"
        rlRun "curl --silent $BACKEND_URL/results/$PROJECT_F/$CHROOT/devel/repodata/ | grep \"404.*Not Found\"" 0

        rlRun "copr-cli build $PROJECT_T $HELLO"
        rlRun "curl --silent $BACKEND_URL/results/$PROJECT_T/$CHROOT/devel/repodata/ | grep -E \"404.*Not Found\"" 1
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject "$PROJECT_T"
        cleanProject "$PROJECT_F"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
