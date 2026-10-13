# coding: utf-8

"""
Signing and unsigning packages
"""

import os
from subprocess import PIPE, Popen

from packaging import version

from copr_backend.signer.obs_sign import OBSSign

from .exceptions import CoprSignError, CoprSignNoKeyError


def get_signer(fullname, opts, log):
    """
    Return a signer object that is appropriate for this Copr instance and project.
    """
    ownername, projectname = fullname.split("/")

    # Ideally we would have automatic discovery of third-party signing plugins
    # but since there is only one known implementation at the moment, let's
    # keep it simple and hardcode it here.
    if "redhat" in opts.signers:
        # pylint: disable=import-outside-toplevel,no-name-in-module
        from copr_backend.signer.redhat_sign import RedHatSign
        signer = RedHatSign(opts, log)
        if signer.has_key(ownername, projectname):
            return signer

    if "obs-sign" in opts.signers:
        # If `obs-sign` is enabled, we don't want to check the key availability
        # and just use it.
        return OBSSign(opts, log)

    raise CoprSignError("No tool for signing available")


def gpg_hashtype_for_chroot(chroot, opts):
    """
    Given the chroot name (in "mock format", like "fedora-rawhide-x86_64")
    return the expected GPG hash type.
    """
    # pylint: disable=too-many-return-statements

    el_chroots = ["rhel", "epel", "centos", "oraclelinux"]

    parts = chroot.split("-")

    version_part = parts[-2]

    if opts.gently_gpg_sha256:
        # For a few weeks we would use the sha256 hash type only for EL8+.
        # This is a safety belt, in case of any failure we'll just re-sign
        # epel-8+ and not _all_ the package data on backend.
        if parts[0] in el_chroots:
            el_version = version_part
            if el_version in ["rawhide"]:
                return "sha256"
            if version.parse(el_version) > version.parse("7"):
                return "sha256"
        return "sha1"

    if parts[0] in el_chroots:
        chroot_version = version_part
        if chroot_version in ["rawhide"]:
            return "sha256"
        if version.parse(chroot_version) <= version.parse("4"):
            return "sha1"
    if parts[0] == "fedora" and parts[1].isnumeric():
        # Fedora 27 moved to RPM v2.14 with the OpenSSL backend.
        if int(parts[1]) < 27:
            return "sha1"
    # fallback to sha256
    return "sha256"


def sign_rpms_in_dir(username, projectname, path, chroot, opts, log):
    """
    Signs rpms using obs-signd.

    If some some pkgs failed to sign, entire build marked as failed,
    but we continue to try sign other pkgs.

    :param username: copr username
    :param projectname: copr projectname
    :param path: directory with rpms to be signed
    :param chroot: chroot name where we sign packages, affects the hash type
    :param Munch opts: backend config

    :type log: logging.Logger

    :raises: :py:class:`backend.exceptions.CoprSignError` failed to sign at least one package
    """

    rpm_list = [
        os.path.join(path, filename.name)
        for filename in os.scandir(path)
        if filename.name.endswith(".rpm")
    ]

    if not rpm_list:
        return

    hashtype = gpg_hashtype_for_chroot(chroot, opts)
    fullname = f"{username}/{projectname}"
    signer = get_signer(fullname, opts, log)

    try:
        signer.get_pubkey(username, projectname, opts.sign_domain)
    except CoprSignNoKeyError:
        signer.create_user_keys(username, projectname, try_indefinitely=True)

    errors = []  # tuples (rpm_filepath, exception)
    for rpm in rpm_list:
        try:
            gpg_email = signer.create_gpg_email(username, projectname, opts.sign_domain)
            signer.sign_one(rpm, gpg_email, hashtype)
            log.info("signed rpm: %s", rpm)

        except CoprSignError as e:
            log.exception("failed to sign rpm: %s", rpm)
            errors.append((rpm, e))

    if errors:
        raise CoprSignError("Rpm sign failed, affected rpms: {}"
                            .format([err[0] for err in errors]))




def _unsign_one(path, log):
    # Requires rpm-sign package.
    # rpm --delsign on an unsigned RPM is a no-op (exit code 0).
    cmd = ["/usr/bin/rpm", "--delsign", path]
    log.info("Unsigning %s, command: %s", path, " ".join(cmd))
    handle = Popen(cmd, stdout=PIPE, stderr=PIPE, encoding="utf-8")
    stdout, stderr = handle.communicate()

    if handle.returncode != 0:
        err = CoprSignError(
            msg="Failed to unsign {}".format(path),
            return_code=handle.returncode,
            cmd=cmd, stdout=stdout, stderr=stderr)

        raise err

    return stdout, stderr


def unsign_rpms_in_dir(path, opts, log):
    """
    :param path: directory with rpms to be signed
    :param Munch opts: backend config
    :type log: logging.Logger
    :raises: :py:class:`backend.exceptions.CoprSignError` failed to sign at least one package
    """
    rpm_list = [
        os.path.join(path, filename.name)
        for filename in os.scandir(path)
        if filename.name.endswith(".rpm")
        ]

    if not rpm_list:
        return

    errors = []  # tuples (rpm_filepath, exception)
    for rpm in rpm_list:
        try:
            _unsign_one(rpm, log)
            log.info("unsigned rpm: %s", rpm)

        except CoprSignError as e:
            log.exception("failed to unsign rpm: %s", rpm)
            errors.append((rpm, e))

    if errors:
        raise CoprSignError("Rpm unsign failed, affected rpms: {}"
                            .format([err[0] for err in errors]))


def resign_rpms_in_dir(username, projectname, path, chroot, opts, log):
    """
    Drop old signatures coming from original repo and re-sign.
    """
    # pylint: disable=too-many-positional-arguments
    unsign_rpms_in_dir(path, opts=opts, log=log)
    if opts.do_sign:
        sign_rpms_in_dir(username, projectname, path, chroot, opts=opts, log=log)
