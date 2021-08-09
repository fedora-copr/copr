# coding: utf-8

"""
Wrapper for /bin/sign from obs-sign package
"""

from subprocess import Popen, PIPE, SubprocessError
import json

import os
from requests import request

from .exceptions import CoprSignError, CoprSignNoKeyError, \
    CoprKeygenRequestError


SIGN_BINARY = "/bin/sign"
DOMAIN = "fedorahosted.org"


def create_gpg_email(username, projectname):
    """
    Creates canonical name_email to identify gpg key
    """

    return "{}#{}@copr.{}".format(username, projectname, DOMAIN)


def call_sign_bin(cmd, log):
    """
    Call /bin/sign and return (rc, stdout, stderr).  Re-try the call
    automatically upon certain failures (if that makes sense).
    """
    cmd_pretty = ' '.join(cmd)
    for attempt in [1, 2, 3]:
        log.info("Calling '%s' (attempt #%s)", cmd_pretty, attempt)
        try:
            handle = Popen(cmd, stdout=PIPE, stderr=PIPE, encoding="utf-8")
            stdout, stderr = handle.communicate()
        except (SubprocessError, OSError) as err:
            new_err = CoprSignError("Failed to invoke '{}'".format(cmd_pretty))
            raise new_err from err

        if handle.returncode != 0 and "Connection timed out" in stderr:
            log.warning("Timeout on %s, re-trying", cmd_pretty)
            continue
        break
    return handle.returncode, stdout, stderr


def get_pubkey(username, projectname, log, outfile=None):
    """
    Retrieves public key for user/project from signer host.

    :param outfile: [optional] file to write obtained key
    :return: public keys

    :raises CoprSignError: failed to retrieve key, see error message
    :raises CoprSignNoKeyError: if there are no such user in keyring
    """
    usermail = create_gpg_email(username, projectname)
    cmd = [SIGN_BINARY, "-u", usermail, "-p"]

    returncode, stdout, stderr = call_sign_bin(cmd, log)
    if returncode != 0:
        if "unknown key:" in stderr:
            raise CoprSignNoKeyError(
                "There are no gpg keys for user {} in keyring".format(username),
                return_code=returncode,
                cmd=cmd, stdout=stdout, stderr=stderr)
        raise CoprSignError(
            msg="Failed to get user pubkey\n"
                "sign stdout: {}\n sign stderr: {}\n".format(stdout, stderr),
            return_code=returncode,
            cmd=cmd, stdout=stdout, stderr=stderr)

    if outfile:
        with open(outfile, "w") as handle:
            handle.write(stdout)

    return stdout


def _sign_one(path, email, log):
    cmd = [SIGN_BINARY, "-u", email, "-r", path]
    returncode, stdout, stderr = call_sign_bin(cmd, log)
    if returncode != 0:
        raise CoprSignError(
            msg="Failed to sign {} by user {}".format(path, email),
            return_code=returncode,
            cmd=cmd, stdout=stdout, stderr=stderr)
    return stdout, stderr


def sign_rpms_in_dir(username, projectname, path, opts, log):
    """
    Signs rpms using obs-signd.

    If some some pkgs failed to sign, entire build marked as failed,
    but we continue to try sign other pkgs.

    :param username: copr username
    :param projectname: copr projectname
    :param path: directory with rpms to be signed
    :param Munch opts: backend config

    :type log: logging.Logger

    :raises: :py:class:`backend.exceptions.CoprSignError` failed to sign at least one package
    """
    rpm_list = [
        os.path.join(path, filename)
        for filename in os.listdir(path)
        if filename.endswith(".rpm")
    ]

    if not rpm_list:
        return

    try:
        get_pubkey(username, projectname, log)
    except CoprSignNoKeyError:
        create_user_keys(username, projectname, opts)

    errors = []  # tuples (rpm_filepath, exception)
    for rpm in rpm_list:
        try:
            _sign_one(rpm, create_gpg_email(username, projectname), log)
            log.info("signed rpm: {}".format(rpm))

        except CoprSignError as e:
            log.exception("failed to sign rpm: {}".format(rpm))
            errors.append((rpm, e))

    if errors:
        raise CoprSignError("Rpm sign failed, affected rpms: {}"
                            .format([err[0] for err in errors]))


def create_user_keys(username, projectname, opts):
    """
    Generate a new key-pair at sign host

    :param username:
    :param projectname:
    :param opts: backend config

    :return: None
    """
    data = json.dumps({
        "name_real": "{}_{}".format(username, projectname),
        "name_email": create_gpg_email(username, projectname)
    })

    keygen_url = "http://{}/gen_key".format(opts.keygen_host)
    query = dict(url=keygen_url, data=data, method="post")
    try:
        response = request(**query)
    except Exception as e:
        raise CoprKeygenRequestError(
            msg="Failed to create key-pair for user: {},"
                " project:{} with error: {}"
            .format(username, projectname, e), request=query)

    if response.status_code >= 400:
        raise CoprKeygenRequestError(
            msg="Failed to create key-pair for user: {}, project:{}, status_code: {}, response: {}"
            .format(username, projectname, response.status_code, response.text),
            request=query, response=response)


def _unsign_one(path):
    # Requires rpm-sign package
    cmd = ["/usr/bin/rpm", "--delsign", path]
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
        os.path.join(path, filename)
        for filename in os.listdir(path)
        if filename.endswith(".rpm")
        ]

    if not rpm_list:
        return

    errors = []  # tuples (rpm_filepath, exception)
    for rpm in rpm_list:
        try:
            _unsign_one(rpm)
            log.info("unsigned rpm: {}".format(rpm))

        except CoprSignError as e:
            log.exception("failed to unsign rpm: {}".format(rpm))
            errors.append((rpm, e))

    if errors:
        raise CoprSignError("Rpm unsign failed, affected rpms: {}"
                            .format([err[0] for err in errors]))
