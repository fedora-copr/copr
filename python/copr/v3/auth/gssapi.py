"""
Authentication via GSSAPI
"""

import requests

try:
    import requests_gssapi
except ImportError:
    requests_gssapi = None

from future.utils import raise_from
from copr.v3.exceptions import CoprAuthException
from copr.v3.requests import munchify, handle_errors
from copr.v3.auth.base import BaseAuth


class Gssapi(BaseAuth):
    """
    Authentication via GSSAPI (i.e. Kerberos)
    """
    def __init__(self, *args, **kwargs):
        """
        Gssapi class stub for the systems where requests_gssapi is not
        installed (typically PyPI installations)
        """
        if not requests_gssapi:
            # Raise an exception if any dependency is not installed
            raise CoprAuthException(
                "The 'requests_gssapi' package is not installed. "
                "Please install it, or use the API token (config file)."
            )
        super(Gssapi, self).__init__(*args, **kwargs)

    def make_expensive(self):
        url = self.config["copr_url"] + "/api_3/gssapi_login/"
        auth = requests_gssapi.HTTPSPNEGOAuth(opportunistic_auth=True)
        try:
            response = requests.get(url, auth=auth)
        except requests_gssapi.exceptions.SPNEGOExchangeError as err:
            msg = "Can not get session for {0} cookie via GSSAPI: {1}".format(
                self.config["copr_url"], err)
            raise_from(CoprAuthException(msg), err)

        handle_errors(response)
        data = munchify(response)
        token = response.cookies.get("session")
        self.username = data.name
        self.cookies = {"session": token}
