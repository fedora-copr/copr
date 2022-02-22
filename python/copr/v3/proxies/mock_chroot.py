from __future__ import absolute_import

from . import BaseProxy
from ..requests import munchify
from ..helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class MockChrootProxy(BaseProxy):

    def get_list(self, pagination=None):
        # TODO: implement pagination
        """List all currently available chroots.

        :return: Munch
        """
        endpoint = "/mock-chroots/list"
        response = self.request.send(endpoint=endpoint)
        return munchify(response)
