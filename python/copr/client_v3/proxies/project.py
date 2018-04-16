from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, POST
from ..exceptions import CoprValidationException


class ProjectProxy(BaseProxy):

    def get(self, ownername, projectname):
        endpoint = "/project"
        data = {
            "ownername": ownername,
            "projectname": projectname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=data)
        response = request.send()
        return response.munchify()
