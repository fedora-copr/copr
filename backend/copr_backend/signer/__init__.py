"""
Base class for RPM signing tools.
"""

import time
from subprocess import PIPE, Popen, SubprocessError

from copr_backend.exceptions import CoprSignError


class BaseSign:
    """
    Base class for signing tools.
    Make sure to extend it and implement the missing functions.
    """

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def create_gpg_email(self, username, projectname, domain):
        """
        Creates canonical name_email to identify gpg key
        """
        raise NotImplementedError

    def get_pubkey(self, username, projectname, sign_domain, outfile=None):
        """
        Retrieves public key for user/project from signer host.

        :param sign_domain: the domain name of the sign key
        :param outfile: [optional] file to write obtained key
        :return: public keys

        :raises CoprSignError: failed to retrieve key, see error message
        :raises CoprSignNoKeyError: if there are no such user in keyring
        """
        raise NotImplementedError

    def sign_one(self, path, email, hashtype):
        """
        Sign one RPM package
        """
        raise NotImplementedError

    def create_user_keys(self, username, projectname, try_indefinitely=False):
        """
        Generate a new key-pair at sign host

        :param username:
        :param projectname:
        :param opts: backend config

        :return: None
        """
        raise NotImplementedError

    def call_sign_bin(self, cmd):
        """
        Call /bin/sign and return (rc, stdout, stderr).  Re-try the call
        automatically upon certain failures (if that makes sense).
        """
        cmd_pretty = ' '.join(cmd)
        for attempt in [1, 2, 3]:
            self.log.info("Calling '%s' (attempt #%s)", cmd_pretty, attempt)
            try:
                # pylint: disable=consider-using-with
                handle = Popen(cmd, stdout=PIPE, stderr=PIPE, encoding="utf-8")
                stdout, stderr = handle.communicate()
            except (SubprocessError, OSError) as err:
                new_err = CoprSignError(f"Failed to invoke '{cmd_pretty}'")
                raise new_err from err

            if handle.returncode != 0:
                self.log.warning("Command '%s' failed with: %s",
                                 cmd_pretty, stderr.rstrip())
                sleeptime = 20
                self.log.warning("Going to sleep %ss and re-try.", sleeptime)
                time.sleep(sleeptime)
                continue
            break
        return handle.returncode, stdout, stderr
