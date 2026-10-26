Exporting a public key with a custom UID
========================================

``gen-clean-pubkey`` exports a public key from the Copr keygen keyring with a
**custom UID of your choice**, without modifying the production keyring and
without the script ever touching private key material.

Usage
-----

.. code-block:: sh

    runuser -u copr-signer -- gen-clean-pubkey \
        '@foo#proj1@copr.fedorahosted.org' \
        '@foo' 'foo@copr.example.cz' > foo-pubkey.asc

===============  =============================================================
argument         meaning
===============  =============================================================
``KEY``          key selector — anything gpg understands (UID substring,
                 e-mail, fingerprint; a fingerprint is the safest choice)
``UID_NAME``     "Name-Real" of the new UID, e.g. ``@foo``
``UID_EMAIL``    e-mail of the new UID; the **only** UID in the output
===============  =============================================================

The example produces an armored key with a single UID
``@foo <foo@copr.example.cz>``.

Background
----------

Copr keys are named ``owner#project@copr.<sign_domain>`` (see
``create_gpg_email()`` in ``backend/copr_backend/sign.py``; the domain
comes from the ``[backend] sign_domain`` config option).  Everything in
the signing chain — keygen's ``user_exists()``, signd's ``/bin/sign -u``,
the backend's ``get_pubkey()`` — looks keys up by this UID e-mail.

Sometimes you want to hand out a public key that shows a different
identity (your own domain instead of ``copr.fedorahosted.org``, a group
name instead of a random project).  Two facts constrain how that can be
done:

1. **An OpenPGP UID must be self-signed**, and a self-signature can only
   be created by the key's *secret* key.  You cannot just staple a UID
   onto a public key — otherwise anyone could claim anyone's key.  So
   somewhere, the secret key must sign the new UID.
2. Signature verification never looks at UIDs — it goes by key
   fingerprint.  A public key with an extra UID but the same key material
   verifies signatures made by the original key normally.

The design goal of this script: the secret key signs the new UID through
**the same sanctioned path used for signing RPMs** (the production
gpg/gpg-agent via ``gpg-copr``), while the script itself only ever
handles public key data:

1. export the public key from the production keyring (read-only),
2. import it into a scratch keyring (``--no-default-keyring --keyring``)
   inside a neutral temporary homedir,
3. add the new UID with ``--quick-add-uid`` — gpg writes the result to
   the *scratch* keyring only; the certification itself is performed by
   the production gpg-agent, exactly like any other signature,
4. export from the scratch keyring with
   ``--export-filter 'keep-uid=-- uid = UID_NAME <UID_EMAIL>'``, so the
   output contains exactly one UID — the requested one.  The full UID
   string is matched (not just the mailbox) so that a pre-existing UID
   with the same e-mail but a different name does not survive; the
   ``--`` flag makes gpg accept spaces in the value.  The primary-uid
   flag is deliberately not set; with a single UID it is irrelevant,
5. sanity-check the output by parsing the packets with ``--show-keys``
   (UID strings are base64-encoded inside the armor, grepping the file is
   meaningless), then print it to stdout.

The scratch keyring (public data only) lives in a ``mktemp -d`` directory
and is removed on exit.  No copies of the keyring, no symlinks to
``private-keys-v1.d``, no ``--export-secret-keys``, no own gpg-agent
(nothing to kill — the agent in use is the production one and is left
alone).

Who touches the private key
---------------------------

Only one step needs the secret key: the UID certification in step 3.
Even there, the ``gpg`` process started by the script never opens any
file under ``private-keys-v1.d/`` — it only connects to the production
gpg-agent socket (``S.gpg-agent``) and submits the signing request
(keygrip + digest), the same mechanism signd uses for signing RPMs.  The
only process that ever opens the private key file is the production
``gpg-agent`` daemon itself (verified with strace).  Steps 1, 4 and 5
are purely public-key operations.

Guarantees
----------

Verified by sha256-comparing the whole production homedir before and
after a run:

- **``pubring.kbx`` (key material) is byte-identical after a run.**
- **``trustdb.gpg`` is never written** (``--trust-model pgp
  --no-auto-check-trustdb``, and no ``--quick-set-primary-uid``, which
  would touch it).
- The **only** side effect on the production homedir is that gpg creates
  an empty ``tofu.db`` (TOFU statistics, an SQLite bookkeeping file) on
  the first run if it does not exist yet.  Repeat runs write nothing at
  all.
- **The output is the same key** — same fingerprint, so RPMs and
  repodata signed by the production key verify against the exported
  public key.
- **The output has exactly one UID**, the requested one (checked, not
  assumed).

Caveats
-------

- Repeated runs produce byte-different but functionally identical output
  (the new self-signature gets a fresh timestamp every run — the scratch
  keyring starts empty each time).
- **The backend's automatic ``pubkey.gpg`` is unaffected.**  Files
  written by the backend into result directories
  (``background_worker_build.py``) are raw signd exports and still
  contain all the original UIDs.  This script produces a pubkey *you*
  distribute manually.
- **Old published pubkeys remain a trace.**  RPM headers carry only the
  key ID / fingerprint (no identity), but anyone holding an old
  ``pubkey.gpg`` with the original UIDs can match the fingerprint.  If
  that matters, clean up the old published pubkey files too.
- **No rollback needed** — the production keyring is never touched;
  deleting the output file undoes everything.
