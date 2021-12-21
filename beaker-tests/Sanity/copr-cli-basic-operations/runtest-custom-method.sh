#!/bin/bash

. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

export RESULTDIR=`mktemp -d`


cleanup_resultdir ()
(
    rm -rf "$RESULTDIR/*"
)

check_resultdir ()
(
    set -e
    cd "$RESULTDIR/fedora-rawhide-x86_64"
    # @FIXME
    #test -f "$RESULTDIR"/script
    for i in $FILES; do
        echo "checking that $i exists in resultdir"
        test -f "$i"
    done

    NV=$1

    echo "checking that only one srpm exists"
    set -- *.src.rpm
    test 1 -eq "$#"

    echo "checking that srpm version is fine"
    case $1 in
        $NV*.src.rpm) ;; # OK
        *) false ;;
    esac
)

check_http_status ()
{
   grep "HTTP/1.1 $1" "$rlRun_LOG" || {
       echo "failed"
       grep "HTTP/1.1 " "$rlRun_LOG"
       false
   }
}

quick_package_script ()
{
    cp "$HERE/files/quick-package.sh" script
    echo "$1" >> script
}


rlJournalStart
    rlPhaseStartSetup
        setup_checks
    rlPhaseEnd

    rlPhaseStartTest Test
    rlRun "export WORKDIR=\`mktemp -d\`"
    rlRun "test -n \"\$WORKDIR\""

    rlRun 'cd "$WORKDIR"'
    rlRun "echo workdir: $WORKDIR"


    PROJECT=custom-1-$NAME_VAR
    rlLogInfo "Create the project $PROJECT"
    rlRun 'copr-cli create "$PROJECT" --chroot fedora-rawhide-x86_64'


    rlLogInfo "Test add-package && build"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script generate_specfile'
    rlRun 'copr add-package-custom "$PROJECT" \
        --name quick-package \
        --script script \
        --script-chroot fedora-rawhide-x86_64'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "Test edit-package && --resultdir"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script "DESTDIR=rrr generate_specfile"'
    rlRun 'copr edit-package-custom "$PROJECT" \
        --name quick-package \
        --script script \
        --script-chroot fedora-rawhide-x86_64'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    # Should fail, there's no spec file in expected resultdir=.
    rlRun 'copr watch-build $BUILD_ID' 4

    rlRun 'copr edit-package-custom "$PROJECT" \
        --name quick-package \
        --script script \
        --script-resultdir rrr \
        --script-chroot fedora-rawhide-x86_64'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "Test that builddeps get propagated"
    builddeps="automake autoconf spax"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script "BUILDDEPS=xxx generate_specfile"'
    rlRun 'copr edit-package-custom "$PROJECT" \
        --name quick-package \
        --script-resultdir "" \
        --script script \
        --script-builddeps "$builddeps" \
        --script-chroot fedora-rawhide-x86_64'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    # Invalid BUILDDEPS value, should fail
    rlRun 'copr watch-build $BUILD_ID' 4

    rlRun 'quick_package_script "BUILDDEPS=\"$builddeps\" generate_specfile"'
    rlRun 'copr edit-package-custom "$PROJECT" \
        --name quick-package \
        --script script \
        --script-builddeps "$builddeps" \
        --script-chroot fedora-rawhide-x86_64'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    # valid BUILDDEPS, this should succeed
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "check that hook_payload get's created"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script "HOOK_PAYLOAD=: generate_specfile"'
    rlRun 'copr edit-package-custom "$PROJECT" \
        --name quick-package \
        --script script \
        --script-chroot fedora-rawhide-x86_64 \
        --webhook-rebuild on'
    rlRun -s 'copr build-package "$PROJECT" --name quick-package --nowait'
    rlRun 'parse_build_id'
    rlLogInfo "Still should fail, since this build is not triggered by webhook."
    rlRun 'copr watch-build $BUILD_ID' 4

    copr_id=$(curl "$FRONTEND_URL/api_3/project?ownername=$USER&projectname=$PROJECT" | jq '.id')
    trigger_url="$FRONTEND_URL/webhooks/custom/$copr_id/webhook_secret/quick-package/"
    rlRun -s 'curl -I "$trigger_url"' 0 # GET can't work
    rlRun 'check_http_status 405'

    content_type_option=' -H "Content-Type: application/json"'
    data_option=' --data '\''{"a": "b"}'\'

    rlLogInfo "full cmd would be: curl -X POST $content_type_option $data_option $trigger_url"
    rlRun "build_id=\$(curl -X POST $data_option \"$trigger_url\")" 0
    rlLogInfo "Still fails since the POST data are not json"
    rlRun 'copr watch-build $BUILD_ID' 4

    rlLogInfo "Still fails since the POST data are not json"
    rlRun "build_id=\$(curl -X POST $content_type_option $data_option \"$trigger_url\")" 0
    rlLogInfo "Should succeed finally"
    # @FIXME
    # rlRun 'copr watch-build $build_id'
    # rlRun 'copr download-build $build_id --dest $RESULTDIR'
    # rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "basic buildcustom command, with fedora-latest-x86_64 chroot (default)"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script "generate_specfile"'
    rlRun -s "copr buildcustom $PROJECT --script script --nowait"
    rlRun 'parse_build_id'
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "buildcustom with --builddeps"
    builddeps='libarchive-devel'
    rlRun 'cleanup_resultdir'
    rlRun "quick_package_script 'BUILDDEPS=\"$builddeps\" generate_specfile'"
    rlRun -s "copr buildcustom $PROJECT --script script --script-builddeps \"$builddeps\" --nowait"
    rlRun 'parse_build_id'
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "buildcustom with --builddeps and --resultdir"
    destdir=abc
    rlRun 'cleanup_resultdir'
    rlRun "quick_package_script 'BUILDDEPS=\"$builddeps\" DESTDIR=$destdir generate_specfile'"
    rlRun -s "copr buildcustom $PROJECT --script script --script-resultdir=$destdir --script-builddeps \"$builddeps\" --nowait"
    rlRun 'parse_build_id'
    rlRun 'copr watch-build $BUILD_ID'
    rlRun 'copr download-build $BUILD_ID --dest $RESULTDIR'
    rlRun 'FILES="success" check_resultdir quick-package-0-0'


    rlLogInfo "Test too-long package name failure"
    rlRun 'cleanup_resultdir'
    rlRun 'quick_package_script generate_specfile'
    package_name="8393c911463547b196d8914faa0b00848393c911463547b196d8914faa0b00848393c911463547b196d8914faa0b008412345678"
    rlRun 'sed -i "s/Name.*$/Name: $package_name/g" script'
    rlRun -s "copr buildcustom '$PROJECT' \
        --script script \
        --script-chroot fedora-rawhide-x86_64 \
        --nowait"
    rlRun 'parse_build_id'
    rlRun "copr watch-build $BUILD_ID" 4
    rlRun "wget $BACKEND_URL/results/$USER/$PROJECT/srpm-builds/$(printf %08d "$BUILD_ID")/backend.log.gz"
    rlRun "zcat backend.log.gz |grep 'Too long package name'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun 'cleanup_resultdir'
        cleanProject "custom-1-$NAME_VAR"
    rlPhaseEnd

rlJournalPrintText
rlJournalEnd
