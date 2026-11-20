#! /bin/bash

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Load config settings
HERE=$(dirname "$(realpath "$0")")
source "$HERE/config"
source "$HERE/helpers"

COMPS_XML='<comps>
  <group>
    <id>nfs-file-server</id>
    <name>NFS File Server</name>
    <description>NFS server tools</description>
    <packagelist>
      <packagereq type="mandatory">nfs-utils</packagereq>
    </packagelist>
  </group>
</comps>'

rlJournalStart
    rlPhaseStartSetup
        setup_checks
        workdirSetup
        setupProjectName "comps-xml"
    rlPhaseEnd

    rlPhaseStartTest
        # Create a new project and wait until the repository is initialized
        rlRun "copr-cli create --chroot $CHROOT $PROJECT"
        if [[ $STORAGE == "pulp" ]]; then
            repomd="${PULP_CONTENT_URL%/}/$PROJECT/$CHROOT/repodata/repomd.xml"
        else
            repomd="${BACKEND_URL%/}/results/$PROJECT/$CHROOT/repodata/repomd.xml"
        fi
        rlRun "wait_for_url '$repomd'"

        # Edit the project chroot and upload comps.xml
        echo "$COMPS_XML" > comps.xml
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --upload-comps comps.xml"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT | grep '\"comps_name\": \"comps.xml\"'"

        # Make sure repodata contains the comps.xml file
        wait_for_no_pending_actions || true
        comps_pattern='repodata/[^"]+-comps\.xml(\.gz)?'
        repomd_xml=$(curl -fsSL "$repomd")
        comps_href=$(grep -oE "$comps_pattern" <<< "$repomd_xml" | head -n 1)
        rlAssertNotEquals "Comps href in $repomd" "$comps_href" ""
        rlRun "curl -fsSL '${repomd%/repodata/repomd.xml}/$comps_href' -o published-comps"

        # Check that it contains the expected XML
        # We cannot easily compare it as a text with $COMPS_XML because Pulp
        # deconstructs the file on upload, saves the values to database and then
        # reconstructs it on the fly. So it won't be bit compatible
        if [[ $STORAGE == "backend" ]]; then
            rlRun "gzip -dc published-comps > published-comps.xml"
        else
            rlRun "mv published-comps published-comps.xml"
        fi
        rlAssertGrep '<name>NFS File Server</name>' published-comps.xml
        rlAssertGrep '<description>NFS server tools</description>' published-comps.xml

        # Edit the project chroot, remove the comps.xml, and make sure it is
        # not contained in the repodata anymore
        rlRun "copr-cli edit-chroot $PROJECT/$CHROOT --delete-comps"
        rlRun "copr-cli get-chroot $PROJECT/$CHROOT | grep '\"comps_name\": null'"
        wait_for_no_pending_actions || true
        repomd_xml=$(curl -fsSL "$repomd")
        rlAssertEquals "Fetch $repomd after deleting comps" "$?" 0
        rlRun "grep -qE '$comps_pattern' <<< \"\$repomd_xml\"" 1
    rlPhaseEnd

    rlPhaseStartCleanup
        cleanProject
        workdirCleanup
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd
