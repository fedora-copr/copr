from __future__ import absolute_import

import os
import json
import time
import requests
from copr.v3.helpers import List
from munch import Munch
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from .exceptions import CoprRequestException, CoprNoResultException, CoprTimeoutException, CoprAuthException


GET = "GET"
POST = "POST"
PUT = "PUT"
DELETE = "DELETE"


class Request(object):
    # This should be a replacement of the _fetch method from APIv1
    # We can have Request, FileRequest, AuthRequest/UnAuthRequest, ...

    def __init__(self, api_base_url=None, connection_attempts=1):
        """
        :param api_base_url:
        :param connection_attempts:

        @TODO maybe don't have both params and data, but rather only one variable
        @TODO and send it as data on POST and as params on GET
        """
        self.api_base_url = api_base_url
        self.connection_attempts = connection_attempts

    def endpoint_url(self, endpoint, params=None):
        params = params or {}
        endpoint = endpoint.strip("/").format(**params)
        return os.path.join(self.api_base_url, endpoint)

    def send(self, endpoint, method=GET, data=None, params=None, headers=None,
             auth=None):

        request_params = self._request_params(
            endpoint, method, data, params, headers, auth)

        response = self._send_request_repeatedly(request_params, auth)

        handle_errors(response)
        return response

    def _send_request_repeatedly(self, request_params, auth):
        """
        Repeat the request until it succeeds, or connection retry reaches its limit.
        """
        sleep = 5
        for i in range(1, self.connection_attempts + 1):
            try:
                response = requests.request(**request_params)
                if response.status_code == 401 and i < self.connection_attempts:
                    # try to authenticate again, don't sleep!
                    self._update_auth_params(request_params, auth, reauth=True)
                    continue
                # Return the response object (even for non-200 status codes!)
                return response
            except requests.exceptions.ConnectionError:
                if i < self.connection_attempts:
                    time.sleep(sleep)

        raise CoprRequestException("Unable to connect to {0}.".format(self.api_base_url))

    def _request_params(self, endpoint, method=GET, data=None, params=None,
                        headers=None, auth=None):
        params = {
            "url": self.endpoint_url(endpoint, params),
            "json": data,
            "method": method.upper(),
            "params": params,
            "headers": headers,
        }
        self._update_auth_params(params, auth)
        return params

    def _update_auth_params(self, request_params, auth, reauth=False):
        # pylint: disable=no-self-use
        if not auth:
            return

        auth.make(reauth)
        request_params.update({
            "auth": auth.auth,
            "cookies": auth.cookies,
        })


class FileRequest(Request):
    def __init__(self, files=None, progress_callback=None, **kwargs):
        super(FileRequest, self).__init__(**kwargs)
        self.files = files
        self.progress_callback = progress_callback

    def _request_params(self, *args, **kwargs):
        params = super(FileRequest, self)._request_params(*args, **kwargs)

        data = self.files or {}
        data["json"] = ("json", json.dumps(params["json"]), "application/json")

        callback = self.progress_callback or (lambda x: x)
        m = MultipartEncoder(data)
        params["json"] = None
        params["data"] = MultipartEncoderMonitor(m, callback)
        params["headers"] = {'Content-Type': params["data"].content_type}
        return params


def munchify(response):
    data = response.json()
    if "items" in data:
        return List(items=[Munch(obj) for obj in data["items"]],
                    meta=Munch(data["meta"]), response=response)
    return Munch(data, __response__=response)


def handle_errors(response):
    try:
        response_json = response.json()
        if "error" not in response_json:
            return

        if response.status_code == 403:
            raise CoprAuthException(response_json["error"], response=response)

        if response.status_code == 404:
            raise CoprNoResultException(response_json["error"], response=response)

        if response.status_code == 504:
            raise CoprTimeoutException(response_json["error"], response=response)

        raise CoprRequestException(response_json["error"], response=response)

    except ValueError:
        # When the request timeouted on the apache layer, we couldn't return a
        # nice JSON response and therefore its parsing fails.
        if response.status_code == 504:
            message = response.reason
            if response.request.method == "GET":
                message += "\nConsider using pagination for large queries."

            # We can't raise-from because of EPEL7
            # pylint: disable=raise-missing-from
            raise CoprTimeoutException(message, response=response)

        raise CoprRequestException("Response is not in JSON format, there is probably a bug in the API code.",
                                   response=response)
