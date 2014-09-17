import os

from subprocess import PIPE, Popen
import tempfile

from .exceptions import BadRequestException, GpgErrorException


def check_user_not_exists(app, mail):
    # TODO: check thouth listing fingerprint --colon mode
    location = os.path.join(app.config["PHRASES_DIR"], mail)
    try:
        with open(location) as handle:
            if handle.read():
                raise BadRequestException(
                    "User key-pair already exists (mail: {})".format(mail))
    except IOError:
        "No file, ok"
        pass


def create_passphrase(app, mail, phrase=None):
    if not phrase:
        phrase = "None"

    location = os.path.join(app.config["PHRASES_DIR"], mail)
    with open(location, "w") as handle:
        handle.write(phrase)
        handle.write(os.linesep)
    return location, phrase


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
    :param expire: [optional] days for key to expire, defualt 0 == never expire
    :param name_comment: [optional] comment for key
    :return: (stdout, stderr) from `gpg` invocation
    """
    #TODO with file lock based on usermail

    check_user_not_exists(app, name_email)
    with tempfile.NamedTemporaryFile(delete=False) as out:
        out.write(template.format(
            key_type="RSA",
            key_length=key_length or 2048,
            name_real=name_real,
            comment=name_comment,
            name_email=name_email,
            expire=expire or 0,
        ))

    cmd = [
        app.config["GPG_BINARY"], "-v", "--batch",
        "--homedir", app.config["GNUPG_HOMEDIR"],
        "--gen-key", out.name
    ]

    handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = handle.communicate()

    create_passphrase(app, name_email)

    if handle.returncode == 0:
        # TODO: validate that we really got armored gpg key
        return stdout, stderr
    else:
        raise GpgErrorException(msg=stderr)
