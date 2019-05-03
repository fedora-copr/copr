import traceback
import os
import logging

from subprocess import PIPE, Popen
import tempfile
import sys

from .exceptions import GpgErrorException, KeygenServiceBaseException
from .gpg import gpg_cmd

log = logging.getLogger(__name__)


def get_passphrase_location(app, name_email):
    return os.path.join(app.config["PHRASES_DIR"], name_email)


def ensure_passphrase_exist(app, name_email):
    """ Need this to tell signd server that `name_email` available in keyring
    Key not protected by passphrase, so we write *something* to passphrase file.
    """

    def create():
        with open(location, "w") as handle:
            handle.write("1")
            handle.write(os.linesep)
            log.debug("created passphrase file for {}".format(name_email))

    location = get_passphrase_location(app, name_email)
    try:
        with open(location) as handle:
            content = handle.read()
            if not content:
                create()
    except IOError:
        create()


def user_exists(app, mail):
    """ Checks if the user identified by mail presents in keyring

    :return: bool True when user present
    :raises: GpgErrorException

    """
    cmd = gpg_cmd + ["--list-secret-keys", "--with-colons", "<{0}>".format(mail)]

    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        log.exception(e)
        raise GpgErrorException(msg="unhandled exception during gpg call",
                                cmd=" ".join(cmd), err=e)

    if handle.returncode == 0:
        # TODO: validate that the key is ultimately trusted
        log.debug("user {} has keys in keyring".format(mail))
        ensure_passphrase_exist(app, mail)
        return True
    elif "error reading key" in stderr.decode():
        log.debug("user {} not found in keyring".format(mail))
        return False
    else:
        err = GpgErrorException(msg="unhandled error", cmd=cmd,
                                stdout=stdout.decode(), stderr=stderr.decode())
        log.error(err)
        raise err


template = """
%no-protection
Key-Type: {key_type}
Key-Length: {key_length}
Name-Real: {name_real}
Name-Comment: {comment}
Name-Email: {name_email}
Expire-Date: {expire}
%commit
"""


def create_new_key(
        app,
        name_real, name_email, key_length,
        expire=None, name_comment=None):
    """
    Creates new key for user.
    WARNING! This method doesn't check for the key duplicity.
    :param app: Flask application object

    :param name_real: name for key identification
    :param name_email: email for key identification
    :param key_length: length of key in bytes, accepts 1024 or 2048
    :param expire: [optional] days for key to expire, default 0 == never expire
    :param name_comment: [optional] comment for key
    :return: (stdout, stderr) from `gpg` invocation
    """

    try:
        # ! Don't use context manager with delete=True
        #   TemporaryFile deletes file on .close() not on __exit__()
        out = tempfile.NamedTemporaryFile(delete=False)
    except Exception as e:
        raise KeygenServiceBaseException(
            msg="Failed to create tmp file for gen_key",
            err=e)
    try:
        out.write(template.format(
            key_type="RSA",
            key_length=key_length or 2048,
            name_real=name_real,
            comment=name_comment,
            name_email=name_email,
            expire=expire or 0).encode('utf-8'))
        out.close()
    except Exception as e:
        raise GpgErrorException(msg="Failed to write tmp file for gen_key",
                                err=e)

    cmd = gpg_cmd + ["--batch", "--gen-key", out.name]

    log.debug("CMD: {}".format(' '.join(map(str, cmd))))
    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        log.exception(e)
        err = GpgErrorException(msg="unhandled exception during gpg call",
                                cmd=" ".join(map(str, cmd)), err=e)
        log.error(err)
        raise err

    log.info("returncode: {}".format(handle.returncode))
    log.info("stdout: {}".format(stdout))
    log.info("stderr: {}".format(stderr))
    if handle.returncode == 0:
        # TODO: validate that we really got armored gpg key
        if not user_exists(app, name_email):
            raise GpgErrorException(
                msg="Key was created, but not found in keyring"
                    "this shouldn't be possible")
        log.info("Created key-pair for: {} ".format(name_email))
    else:
        raise GpgErrorException(msg=stderr.decode())

    try:
        os.remove(out.name)
    except Exception as e:
        log.error(e)
