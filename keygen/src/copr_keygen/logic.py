import os

from subprocess import PIPE, Popen
import tempfile

from .exceptions import GpgErrorException


def ensure_passphrase_exist(app, name_email):
    """ Need this to tell signd server that `name_email` available in keyring
    Key not protected by passphrase, so we write *something* to passphrase file.
    """
    def create():
        with open(location, "w") as handle:
            handle.write("1")
            handle.write(os.linesep)

    location = os.path.join(app.config["PHRASES_DIR"], name_email)
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
    cmd = [app.config["GPG_BINARY"],
           "--homedir", app.config["GNUPG_HOMEDIR"],
           "--list-secret-keys", "--with-colons", mail]

    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        raise GpgErrorException(msg="unhandled exception during gpg call",
                                cmd=" ".join(cmd), err=e)

    if handle.returncode == 0:
        # TODO: validate that we really got exactly one line in stdout
        ensure_passphrase_exist(app, mail)
        return True
    elif "error reading key" in stderr:
        return False
    else:
        raise GpgErrorException(msg="unhandled error", cmd=cmd, stdout=stdout,
                                stderr=stderr)


template = """
%no-ask-passphrase
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
    :param app: Flask application object

    :param name_real: name for key identification
    :param name_email: email for key identification
    :param key_length: length of key in bytes, accepts 1024 or 2048
    :param expire: [optional] days for key to expire, default 0 == never expire
    :param name_comment: [optional] comment for key
    :return: (stdout, stderr) from `gpg` invocation
    """

    #TODO with file lock based on usermail !!!

    if user_exists(app, name_email):
        return

    with tempfile.NamedTemporaryFile() as out:
        out.write(template.format(
            key_type="RSA",
            key_length=key_length or 2048,
            name_real=name_real,
            comment=name_comment,
            name_email=name_email,
            expire=expire or 0))

    cmd = [
        app.config["GPG_BINARY"], "-v", "--batch",
        "--homedir", app.config["GNUPG_HOMEDIR"],
        "--gen-key", out.name
    ]

    try:
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
    except Exception as e:
        raise GpgErrorException(msg="unhandled exception during gpg call",
                                cmd=" ".join(cmd), err=e)

    if handle.returncode == 0:
        # TODO: validate that we really got armored gpg key
        if not user_exists(app, name_email):
            raise GpgErrorException(
                msg="Key was created, but not found in keyring"
                    "this shouldn't be possible")
    else:
        raise GpgErrorException(msg=stderr)
