"""
OBS Sign (obs-signd) signing backend.
"""

from copr_common.request import SafeRequest

from copr_backend.exceptions import (
    CoprKeygenRequestError,
    CoprSignError,
    CoprSignNoKeyError,
)
from copr_backend.helpers import get_redis_logger
from copr_backend.signer import BaseSign


class OBSSign(BaseSign):
    """
    Sign packages using obs-sign
    https://github.com/openSUSE/obs-sign/tree/master

    This requires configured `/etc/sign.conf` on backend and the copr-keygen
    server running `signd`.
    """

    SIGN_BINARY = "/bin/sign"

    def create_gpg_email(self, username, projectname, domain):
        return f"{username}#{projectname}@copr.{domain}"

    def get_pubkey(self, username, projectname, sign_domain, outfile=None):
        usermail = self.create_gpg_email(username, projectname, sign_domain)
        cmd = [self.SIGN_BINARY, "-u", usermail, "-p"]

        returncode, stdout, stderr = self.call_sign_bin(cmd)
        if returncode != 0:
            if "unknown key:" in stderr:
                raise CoprSignNoKeyError(
                    f"There are no gpg keys for user {username} in keyring",
                    return_code=returncode,
                    cmd=cmd, stdout=stdout, stderr=stderr)
            raise CoprSignError(
                msg=f"Failed to get user pubkey\n"
                    f"sign stdout: {stdout}\n sign stderr: {stderr}\n",
                return_code=returncode,
                cmd=cmd, stdout=stdout, stderr=stderr)

        if outfile:
            with open(outfile, "w", encoding="utf-8") as handle:
                handle.write(stdout)

        return stdout

    def sign_one(self, path, email, hashtype):
        cmd = [self.SIGN_BINARY, "-4", "-h", hashtype, "-u", email, "-r", path]
        returncode, stdout, stderr = self.call_sign_bin(cmd)
        if returncode != 0:
            raise CoprSignError(
                msg=f"Failed to sign {path} by user {email}",
                return_code=returncode,
                cmd=cmd, stdout=stdout, stderr=stderr)
        return stdout, stderr

    def create_user_keys(self, username, projectname, try_indefinitely=False):
        data = {
            "name_real": f"{username}_{projectname}",
            "name_email": self.create_gpg_email(username, projectname, self.opts.sign_domain)
        }

        log = get_redis_logger(self.opts, "sign", "actions")
        keygen_url = f"http://{self.opts.keygen_host}/gen_key"
        query = {"url": keygen_url, "data": data, "method": "post"}
        try:
            request = SafeRequest(log=log, try_indefinitely=try_indefinitely)
            response = request.send(**query)
        except Exception as e:
            raise CoprKeygenRequestError(
                msg=f"Failed to create key-pair for user: {username},"
                    f" project:{projectname} with error: {e}",
                request=query) from e

        if response.status_code >= 400:
            raise CoprKeygenRequestError(
                msg=f"Failed to create key-pair for user: {username}, project:{projectname}, "
                    f"status_code: {response.status_code}, response: {response.text}",
                request=query, response=response)
