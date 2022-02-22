"""
Webhook related actions in APIv3
"""

from __future__ import absolute_import

from . import BaseProxy
from ..requests import munchify, POST
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class WebhookProxy(BaseProxy):
    """
    This class provides access to all webhook related actions in APIv3
    Methods call endpoints that starts with /api_3/webhook/
    """

    def generate(self, ownername, projectname):
        """
        Generate a new webhook secret

        :param str ownername:
        :param str projectname:
        :return: Munch
        """
        endpoint = "/webhook/generate/{ownername}/{projectname}"
        params = {
            "ownername": ownername,
            "projectname": projectname,
        }
        self.request.auth = self.auth
        response = self.request.send(endpoint=endpoint, method=POST, params=params)
        return munchify(response)
