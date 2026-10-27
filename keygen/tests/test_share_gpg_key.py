# pylint: disable=redefined-outer-name

# End-to-end test for run/share-gpg-key.  The script is run with
# $GNUPG_HOME set, so it uses plain gpg against a temporary "production"
# homedir instead of gpg-copr; the code paths exercised are the same.

import os
import subprocess

import pytest

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, "run", "share-gpg-key",
)

OWNER = "@foo"
KEPT_PROJECT = "proj1"
MIGRATED_PROJECTS = ["proj2", "proj3"]  # proj3 never gets its own key


def _gpg(homedir, *args, **kwargs):
    return subprocess.run(
        ("gpg", "--homedir", str(homedir), "--batch") + args,
        check=True, capture_output=True, **kwargs)


def _keygen_key(homedir, name_real, email):
    subprocess.run(
        ("gpg", "--homedir", str(homedir), "--batch",
         "--pinentry-mode", "loopback", "--passphrase", "",
         "--quick-gen-key", f"{name_real} <{email}>",
         "rsa2048", "sign", "0"),
        check=True, capture_output=True)


def _gpg_email(project):
    return f"{OWNER}#{project}@copr.fedorahosted.org"


def _fingerprints(homedir, email):
    # gpg exits with 2 when the pattern matches no key, that is fine here
    result = subprocess.run(
        ("gpg", "--homedir", str(homedir), "--batch",
         "--list-keys", "--with-colons", f"<{email}>"),
        capture_output=True, check=False)
    return [
        line.split(b":")[9].decode()
        for line in result.stdout.splitlines()
        if line.startswith(b"fpr:")
    ]


@pytest.fixture
def keygen_homedir(tmp_path):
    """A temporary homedir standing in for the production keygen one."""
    homedir = tmp_path / "gnupg"
    homedir.mkdir()
    _keygen_key(homedir, f"{OWNER}_{KEPT_PROJECT}", _gpg_email(KEPT_PROJECT))
    _keygen_key(homedir, f"{OWNER}_proj2", _gpg_email("proj2"))
    return homedir


def _run_script(homedir, cwd, dry_run=False):
    args = (SCRIPT, "--ownername", OWNER,
            "--project", KEPT_PROJECT,
            "--project", "proj2",
            "--project", "proj3")
    if dry_run:
        args = args + ("--dry-run",)
    return subprocess.run(
        args,
        env=dict(os.environ, GNUPG_HOME=str(homedir)),
        cwd=str(cwd),
        check=True, capture_output=True)


def test_share_gpg_key(keygen_homedir, tmp_path):
    kept_fingerprint = _fingerprints(keygen_homedir, _gpg_email(KEPT_PROJECT))[0]
    old_proj2_fingerprint = _fingerprints(keygen_homedir, _gpg_email("proj2"))[0]

    result = _run_script(keygen_homedir, cwd=tmp_path)

    # every project's e-mail now resolves to exactly the kept key
    for project in [KEPT_PROJECT] + MIGRATED_PROJECTS:
        assert _fingerprints(keygen_homedir, _gpg_email(project)) == \
            [kept_fingerprint]

    # the old key is gone from the keyring
    stdout = _gpg(keygen_homedir, "--list-keys", "--with-colons").stdout.decode()
    assert old_proj2_fingerprint not in stdout

    # the kept key carries one UID per project, in the keygen format
    stdout = _gpg(keygen_homedir, "--list-keys", "--with-colons",
                  kept_fingerprint).stdout.decode()
    for project in MIGRATED_PROJECTS:
        assert f"{OWNER}_{project} <{_gpg_email(project)}>" in stdout

    # the deleted key was backed up (secret keys included) into the cwd
    backups = list(tmp_path.glob("*key-backup*.asc"))
    assert len(backups) == 1
    assert b"BEGIN PGP PRIVATE KEY BLOCK" in backups[0].read_bytes()

    # the user is told what to do on the backend
    assert b"copr-fix-gpg" in result.stdout
    for project in MIGRATED_PROJECTS:
        assert f"{OWNER}/{project}\n".encode() in result.stdout
        # the kept project needs no re-signing
        assert result.stdout.count(
            f"{OWNER}/{KEPT_PROJECT}\n".encode()) == 0


def test_share_gpg_key_dry_run(keygen_homedir, tmp_path):
    """--dry-run reads the keyring, prints the plan, changes nothing."""
    kept_fingerprint = _fingerprints(keygen_homedir, _gpg_email(KEPT_PROJECT))[0]
    old_proj2_fingerprint = _fingerprints(keygen_homedir, _gpg_email("proj2"))[0]

    result = _run_script(keygen_homedir, cwd=tmp_path, dry_run=True)

    assert b"DRY-RUN: would add UID" in result.stdout
    assert b"DRY-RUN: would delete the key of 'proj2'" in result.stdout
    assert b"DRY-RUN: would back up" in result.stdout
    assert b"DRY-RUN: no changes were made" in result.stdout

    # nothing changed — no backup file, old keys still in place, the
    # kept key carries no new UIDs
    assert not list(tmp_path.glob("*key-backup*"))
    assert _fingerprints(keygen_homedir, _gpg_email("proj2")) == \
        [old_proj2_fingerprint]
    assert _fingerprints(keygen_homedir, _gpg_email("proj3")) == []
    stdout = _gpg(keygen_homedir, "--list-keys", "--with-colons",
                  kept_fingerprint).stdout.decode()
    assert "proj2" not in stdout and "proj3" not in stdout

    # the real run still works afterwards
    _run_script(keygen_homedir, cwd=tmp_path)
    for project in [KEPT_PROJECT] + MIGRATED_PROJECTS:
        assert _fingerprints(keygen_homedir, _gpg_email(project)) == \
            [kept_fingerprint]


def test_share_gpg_key_rerun(keygen_homedir, tmp_path):
    """The script is idempotent — a re-run is a no-op."""
    _run_script(keygen_homedir, cwd=tmp_path)
    _run_script(keygen_homedir, cwd=tmp_path)


def test_share_gpg_key_resume(keygen_homedir, tmp_path):
    """A partial run (UID added, old key not yet deleted) is resumed."""
    kept_fingerprint = _fingerprints(keygen_homedir, _gpg_email(KEPT_PROJECT))[0]
    old_proj2_fingerprint = _fingerprints(keygen_homedir, _gpg_email("proj2"))[0]

    # simulate an interrupted run: the UID was added to the kept key,
    # but the old key was not deleted yet — the e-mail of proj2 now
    # resolves to two keys
    _gpg(keygen_homedir, "--pinentry-mode", "loopback", "--passphrase", "",
         "--quick-add-uid", kept_fingerprint,
         "{}_proj2 <{}>".format(OWNER, _gpg_email("proj2")))

    _run_script(keygen_homedir, cwd=tmp_path)

    # the old key got deleted, the e-mail resolves to the kept key only
    assert _fingerprints(keygen_homedir, _gpg_email("proj2")) == \
        [kept_fingerprint]
    stdout = _gpg(keygen_homedir, "--list-keys", "--with-colons").stdout.decode()
    assert old_proj2_fingerprint not in stdout


def test_share_gpg_key_backup_permissions(keygen_homedir, tmp_path):
    """The backup file holds secret keys — it must stay owner-only."""
    old_umask = os.umask(0o022)
    try:
        _run_script(keygen_homedir, cwd=tmp_path)
    finally:
        os.umask(old_umask)

    backup = next(iter(tmp_path.glob("*key-backup*.asc")))
    assert (backup.stat().st_mode & 0o777) == 0o600
