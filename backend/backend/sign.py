#!/usr/bin/env python
# coding: utf-8

"""
Wrapper for /bin/sign from obs-sign package
"""

from subprocess import Popen, PIPE
import json

import os
from requests import request

from .exceptions import CoprSignError, CoprSignNoKeyError, \
    CoprKeygenRequestError, \
    MockRemoteError


SIGN_BINARY = "/bin/sign"
DOMAIN = "fedorahosted.org"

# TODO: discover from config
# COPR_KEYGEN_URL = "http://127.0.0.1:3872/gen_key"
COPR_KEYGEN_URL = "http://209.132.184.124/gen_key"


def create_gpg_email(username, projectname):
    """
    Creates canonical name_email to identify gpg key
    """
    return "{}_{}@copr.{}".format(username, projectname, DOMAIN)


def get_pubkey(username, projectname, outfile=None):
    """
    Retrieves public key for user/project from signer host.

    :param outfile: [optional] file to write obtained key
    :return: public keys

    :raises: CoprSignError or CoprSignNoKeyError
    """
    usermail = create_gpg_email(username, projectname)
    cmd = ["sudo", SIGN_BINARY, "-u", usermail, "-p"]

    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        raise CoprSignError("Failed to get user pubkey"
                            " due to: {}".format(e))

    if handle.returncode != 0:
        if "unknown key:" in stderr:
            raise CoprSignNoKeyError(
                "There are no gpg keys for user {} in keyring".format(username),
                return_code=handle.returncode,
                cmd=cmd, stdout=stdout, stderr=stderr)
        raise CoprSignError(
            msg="Failed to get user pubkey\n"
                "sign stdout: {}\n sign stderr: {}\n".format(stdout, stderr),
            return_code=handle.returncode,
            cmd=cmd, stdout=stdout, stderr=stderr)

    if outfile:
        with open(outfile, "w") as handle:
            handle.write(stdout)

    return stdout


def _sign_one(path, email, callback=None):
    cmd = ["sudo", SIGN_BINARY, "-u", email, "-r", path]

    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        err = CoprSignError(
            msg="Failed to  invoke sign {} by user {} with error {}"
            .format(path, email, e, cmd=None, stdout=None, stderr=None))

        if callback:
            callback.error(err)
        raise err

    if handle.returncode != 0:
        err = CoprSignError(
            msg="Failed to sign {} by user {}".format(path, email),
            return_code=handle.returncode,
            cmd=cmd, stdout=stdout, stderr=stderr)

        if callback:
            callback.error(err)
        raise err

    return stdout, stderr


def sign_rpms_in_dir(username, projectname, path, callback=None):
    """
    Signs rpms using obs-signd.

    If some some pkgs failed to sign, entire build marked as failed,
    but we continue to try sign other pkgs.


    :param username: copr username
    :param projectname: copr projectname
    :param path: directory with rpms to be signed

    :param .mockremote.DefaultCallBack callback: object to log progress,
        two methods are utilised: ``log`` and ``error``
    """
    rpm_list = [
        os.path.join(path, filename)
        for filename in os.listdir(path)
        if filename.endswith("rpm")
    ]

    try:
        get_pubkey(username, projectname)
    except CoprSignNoKeyError:
        create_user_keys(username, projectname)

    errors = []  # tuples (rpm_filepath, exception)
    for rpm in rpm_list:
        try:
            _sign_one(rpm,
                      create_gpg_email(username, projectname),
                      callback)

            if callback:
                callback.log("signed rpm: {}".format(rpm))

        except CoprSignError as e:
            errors.append((rpm, e))

    if errors:
        raise MockRemoteError("Rpm sign failed, affected rpms: {}"
                              .format([err[0] for err in errors]))


def create_user_keys(username, projectname):
    data = json.dumps({
        "name_real": "{}_{}".format(username, projectname),
        "name_email": create_gpg_email(username, projectname)
    })

    query = dict(url=COPR_KEYGEN_URL, data=data, method="post")
    try:
        response = request(**query)
    except Exception as e:
        raise CoprKeygenRequestError(
            msg="Failed to create key-pair for user: {},"
                " project:{} with error: {}"
            .format(username, projectname, e), request=query)

    if response.status_code >= 400:
        raise CoprKeygenRequestError(
            msg="Failed to create key-pair for user: {}, project:{}"
            .format(username, projectname),
            request=query, response=response)

