"""
Authentication classes for usage within APIv3
"""

from copr.v3.exceptions import CoprAuthException
from copr.v3.auth.token import ApiToken
from copr.v3.auth.gssapi import Gssapi


def auth_from_config(config):
    """
    Decide what authentication method to use and return an appropriate instance
    """
    if config.get("token"):
        return ApiToken(config)

    if config.get("gssapi"):
        return Gssapi(config)

    msg = "GSSAPI disabled and login:token is invalid ({0}:{1})".format(
        config.get("login", "NOT_SET"),
        config.get("token", "NOT_SET"),
    )
    raise CoprAuthException(msg)
