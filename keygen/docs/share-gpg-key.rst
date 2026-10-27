Sharing one GPG key between projects
====================================

``share-gpg-key`` (source ``keygen/run/share-gpg-key``, installed into
``%{_bindir}``) makes one Copr project's GPG key shared by other
projects of the same owner.  Run it as ``copr-signer`` on the keygen
host:

.. code-block:: sh

    runuser -u copr-signer -- share-gpg-key \
        --ownername '@foo' --project proj1 --project proj2 --project proj3

The key of the **first** ``--project`` is kept, one UID per every
additional ``--project`` is added to it, and the additional projects'
own keys are deleted from the keyring.  ``--dry-run`` only prints the
actions that would be taken.

- Before deletion, each key is exported (including the secret key) into
  ``./<owner>-key-backup-<date>.asc`` (mode 0600) unless ``--no-backup``
  is given.  That file is the only way back — move it somewhere safe.
- **Pause builds** for the affected projects while the script runs.
- The script is idempotent, and resumes partially migrated projects.
  It can be run again at any time to share the key with further
  projects — repeat the command with the same kept project and the new
  ones.
- All actions are logged into
  ``/var/log/copr-keygen/share-gpg-key.log``.

The RPMs of the migrated projects still carry signatures of their old
keys — re-sign them on the backend host (as user ``copr``) with
``copr-fix-gpg``.  The script prints the exact instructions at the end.
