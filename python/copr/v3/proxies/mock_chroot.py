from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, munchify


class MockChrootProxy(BaseProxy):

    def get_list(self, pagination=None):
        """List all currently available chroots.

        :return: Munch
        """
        endpoint = "/mock-chroots/list"
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return munchify(response)
