"""
Authentication via GSSAPI
"""

import requests
import requests_gssapi
from future.utils import raise_from
from copr.v3.exceptions import CoprAuthException
from copr.v3.requests import munchify, handle_errors
from copr.v3.auth.base import BaseAuth


class Gssapi(BaseAuth):
    """
    Authentication via GSSAPI (i.e. Kerberos)
    """
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
