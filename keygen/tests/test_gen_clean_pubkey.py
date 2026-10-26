# End-to-end test for run/gen-clean-pubkey.  The script is run with
# $GNUPG_HOME set, so it uses plain gpg against a temporary "production"
# homedir instead of gpg-copr; the code paths exercised are the same.

# pylint: disable=redefined-outer-name

import os
import subprocess

import pytest

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, "run", "gen-clean-pubkey",
)

ORIGINAL_UID_EMAIL = "@foo#proj1@copr.fedorahosted.org"
NEW_NAME = "@foo"
NEW_EMAIL = "foo@copr.example.cz"
NEW_UID = "@foo <foo@copr.example.cz>"


def _gpg(homedir, *args, **kwargs):
    return subprocess.run(
        ("gpg", "--homedir", str(homedir), "--batch") + args,
        check=True, capture_output=True, **kwargs)


def _colon_fields(homedir, field, *args, stdin=None):
    stdout = _gpg(homedir, "--with-colons", *args, input=stdin).stdout
    return [
        line.split(b":")[9].decode()
        for line in stdout.splitlines()
        if line.startswith(field.encode() + b":")
    ]


@pytest.fixture
def keygen_homedir(tmp_path):
    """A temporary homedir standing in for the production keygen one."""
    homedir = tmp_path / "gnupg"
    homedir.mkdir()
    subprocess.run(
        ("gpg", "--homedir", str(homedir), "--batch",
         "--pinentry-mode", "loopback", "--passphrase", "",
         "--quick-gen-key", "Copr <{}>".format(ORIGINAL_UID_EMAIL),
         "rsa2048", "sign", "0"),
        check=True, capture_output=True)
    return homedir


def _run_script(homedir):
    return subprocess.run(
        (SCRIPT, ORIGINAL_UID_EMAIL, NEW_NAME, NEW_EMAIL),
        env=dict(os.environ, GNUPG_HOME=str(homedir)),
        check=True, capture_output=True)


def test_single_requested_uid(keygen_homedir):
    armored = _run_script(keygen_homedir).stdout
    uids = _colon_fields(keygen_homedir, "uid", "--show-keys", stdin=armored)
    assert uids == [NEW_UID]


def test_no_original_identity_in_output(keygen_homedir):
    armored = _run_script(keygen_homedir).stdout
    assert b"fedorahosted" not in armored


def test_same_fingerprint(keygen_homedir):
    armored = _run_script(keygen_homedir).stdout
    exported = _colon_fields(keygen_homedir, "fpr", "--show-keys", stdin=armored)
    original = _colon_fields(keygen_homedir, "fpr", "--list-keys")
    assert exported == original


def test_same_email_different_name(keygen_homedir):
    """A pre-existing UID with the same e-mail but a different name must
    not survive the export filter."""
    _gpg(keygen_homedir, "--pinentry-mode", "loopback", "--passphrase", "",
         "--quick-add-uid", ORIGINAL_UID_EMAIL,
         "Other Name <{}>".format(NEW_EMAIL))
    armored = _run_script(keygen_homedir).stdout
    uids = _colon_fields(keygen_homedir, "uid", "--show-keys", stdin=armored)
    assert uids == [NEW_UID]


def test_signatures_verify(keygen_homedir, tmp_path):
    armored = _run_script(keygen_homedir).stdout

    # sign a file with the original (secret) key
    data = tmp_path / "data"
    data.write_bytes(b"copr")
    signature = tmp_path / "data.sig"
    _gpg(keygen_homedir, "--pinentry-mode", "loopback", "--passphrase", "",
         "--detach-sign", "--output", str(signature), str(data))

    # verify it against the exported public key, in a fresh keyring
    verify_homedir = tmp_path / "verify"
    verify_homedir.mkdir()
    _gpg(verify_homedir, "--import", input=armored)
    _gpg(verify_homedir, "--verify", str(signature), str(data))
