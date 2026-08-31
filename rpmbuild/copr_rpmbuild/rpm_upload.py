"""
Process direct RPM upload tarballs.

Expected tarball structure (.tar.gz):

    upload.tar.gz
    └── upload/                         # exactly one top-level directory
        ├── package-1.0-1.fc40.x86_64.rpm   # required: at least one binary RPM
        ├── package-1.0-1.fc40.src.rpm        # optional: at most one SRPM
        ├── build.log                         # optional: arbitrary extra files
        └── sha256.json                       # optional: filename -> hex digest

All payload files must be regular files directly inside the top-level
directory (no nested subdirectories).  Binary RPM architectures must match
the target chroot or be noarch.  When sha256.json is present, every listed
file is verified; when absent, no checksum validation is performed.
"""

import hashlib
import json
import os
import shutil

from copr_rpmbuild.helpers import get_rpm_header, run_cmd

SHA256_MANIFEST = "sha256.json"
SRPM_SUFFIXES = (".src.rpm", ".nosrc.rpm")

# RPM arch tags that are compatible with a given chroot architecture.
ARCH_COMPATIBILITY = {
    "i386": frozenset({"i386", "i586", "i686"}),
    "armhfp": frozenset({"armhfp", "armv7hl"}),
}


def _is_srpm(filename):
    return filename.endswith(SRPM_SUFFIXES)


def _is_binary_rpm(filename):
    return filename.endswith(".rpm") and not _is_srpm(filename)


def _sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compatible_archs(chroot_arch):
    return ARCH_COMPATIBILITY.get(chroot_arch, frozenset({chroot_arch})) | {"noarch"}


def extract_tarball(tarball_path, dest):
    """
    Extract tarball into dest and return the single top-level content directory.

    :raises RuntimeError: if tarball structure is invalid
    """
    os.makedirs(dest, exist_ok=True)
    run_cmd(
        ["tar", "-xzf", tarball_path, "-C", dest, "--no-same-owner"])

    entries = os.listdir(dest)
    if len(entries) != 1:
        raise RuntimeError(
            "Uploaded tarball must contain exactly one top-level directory")

    content_dir = os.path.join(dest, entries[0])
    if not os.path.isdir(content_dir):
        raise RuntimeError(
            "Uploaded tarball top-level entry must be a directory")

    return content_dir


def verify_sha256_manifest(content_dir, manifest):
    """
    Verify file checksums listed in manifest.

    No-op when manifest is None.
    """
    if manifest is None:
        return

    failures = []
    for filename, expected in manifest.items():
        path = os.path.join(content_dir, filename)
        if not os.path.isfile(path):
            failures.append(
                f"file listed in {SHA256_MANIFEST} not found: {filename}")
            continue

        actual = _sha256_of_file(path)
        if str(expected).lower() != actual.lower():
            failures.append(
                f"SHA256 mismatch for '{filename}': "
                f"expected {expected}, got {actual}")

    if failures:
        raise RuntimeError("\n".join(failures))


def classify_files(content_dir):
    """
    Classify files in the extracted upload directory.

    :returns dict: keys rpms (list), srpm (str|None), logs (list)
    """
    rpms = []
    srpm = None
    logs = []

    for entry in os.listdir(content_dir):
        if entry == SHA256_MANIFEST:
            continue

        path = os.path.join(content_dir, entry)
        if not os.path.isfile(path):
            raise RuntimeError(
                f"Uploaded tarball must contain only files, found: {entry}")

        if _is_binary_rpm(entry):
            rpms.append(entry)
        elif _is_srpm(entry):
            if srpm is not None:
                raise RuntimeError(
                    "Uploaded tarball must contain at most one SRPM")

            srpm = entry
        else:
            logs.append(entry)

    return {"rpms": rpms, "srpm": srpm, "logs": logs}


def validate_binary_rpm_archs(content_dir, rpms, chroot_arch):
    """
    Ensure each binary RPM matches the target chroot architecture.
    """
    allowed_archs = _compatible_archs(chroot_arch)
    for filename in rpms:
        path = os.path.join(content_dir, filename)
        hdr = get_rpm_header(path)
        if hdr["arch"] not in allowed_archs:
            raise RuntimeError(
                "Uploaded RPM {0} has arch '{1}', which doesn't match "
                "chroot '{2}'".format(
                    filename, hdr["arch"], chroot_arch))


def archive_uploaded_logs(log_files, content_dir, resultdir):
    """
    Archive optional log/txt files into uploaded-logs.tar.gz in resultdir.
    """
    if not log_files:
        return

    tarball_path = os.path.join(resultdir, "uploaded-logs.tar.gz")
    run_cmd(
        ["tar", "-czf", tarball_path, "-C", content_dir, "--"]
        + sorted(log_files))


def process_uploaded_tarball(tarball_path, resultdir, chroot):
    """
    Extract, validate and publish a direct RPM upload tarball.

    RPMs and optional SRPM are moved into resultdir.  Optional log/txt
    files are archived into uploaded-logs.tar.gz.
    """
    chroot_arch = chroot.rsplit("-", 1)[-1]
    extract_root = os.path.join(resultdir, ".rpm-upload-extract")
    try:
        content_dir = extract_tarball(tarball_path, extract_root)
        manifest_path = os.path.join(content_dir, SHA256_MANIFEST)
        manifest = None
        if os.path.isfile(manifest_path):
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)

        verify_sha256_manifest(content_dir, manifest)

        classified = classify_files(content_dir)
        if not classified["rpms"]:
            raise RuntimeError(
                "Uploaded tarball must contain at least one binary RPM")

        validate_binary_rpm_archs(
            content_dir, classified["rpms"], chroot_arch)

        for filename in classified["rpms"]:
            shutil.move(
                os.path.join(content_dir, filename),
                os.path.join(resultdir, filename))

        if classified["srpm"]:
            shutil.move(
                os.path.join(content_dir, classified["srpm"]),
                os.path.join(resultdir, classified["srpm"]))

        archive_uploaded_logs(
            classified["logs"], content_dir, resultdir)
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)
