from __future__ import absolute_import

import os
import json
import time
import requests
import requests_gssapi
from copr.v3.helpers import List
from munch import Munch
from future.utils import raise_from
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from .exceptions import CoprRequestException, CoprNoResultException, CoprTimeoutException, CoprAuthException


GET = "GET"
POST = "POST"
PUT = "PUT"


class Request(object):
    # This should be a replacement of the _fetch method from APIv1
    # We can have Request, FileRequest, AuthRequest/UnAuthRequest, ...
    # pylint: disable=too-many-instance-attributes

    def __init__(self, api_base_url=None, auth=None, connection_attempts=1):
        """
        :param endpoint:
        :param api_base_url:
        :param method:
        :param data: dict
        :param params: dict for constructing query params in URL (e.g. ?key1=val1)
        :param auth: tuple (login, token)

        @TODO maybe don't have both params and data, but rather only one variable
        @TODO and send it as data on POST and as params on GET
        """
        self.api_base_url = api_base_url
        self.auth = auth
        self.connection_attempts = connection_attempts
        self._method = GET
        self.endpoint = None
        self.data = None
        self.params = {}
        self.headers = None

    @property
    def endpoint_url(self):
        endpoint = self.endpoint.strip("/").format(**self.params)
        return os.path.join(self.api_base_url, endpoint)

    @property
    def method(self):
        return self._method.upper()

    def send(self, endpoint, method=GET, data=None, params=None, headers=None):
        if params is None:
            self.params = {}
        else:
            self.params = params
        self.endpoint = endpoint
        self._method = method
        self.data = data
        self.headers = headers

        session = requests.Session()
        if not isinstance(self.auth, tuple):
            # api token not available, set session cookie obtained via gssapi
            session.cookies.set("session", self.auth)

        response = self._send_request_repeatedly(session)
        handle_errors(response)
        return response

    def _send_request_repeatedly(self, session):
        """
        Repeat the request until it succeeds, or connection retry reaches its limit.
        """
        sleep = 5
        for i in range(1, self.connection_attempts + 1):
            try:
                response = session.request(**self._request_params)
            except requests_gssapi.exceptions.SPNEGOExchangeError as e:
                raise_from(CoprAuthException("GSSAPI authentication failed."), e)
            except requests.exceptions.ConnectionError:
                if i < self.connection_attempts:
                    time.sleep(sleep)
            else:
                return response
        raise CoprRequestException("Unable to connect to {0}.".format(self.api_base_url))

    @property
    def _request_params(self):
        params = {
            "url": self.endpoint_url,
            "json": self.data,
            "method": self.method,
            "params": self.params,
            "headers": self.headers,
        }
        # We usually use a tuple (login, token). If this is not available,
        # we use gssapi auth, which works with cookies.
        if isinstance(self.auth, tuple):
            params["auth"] = self.auth
        return params


class FileRequest(Request):
    def __init__(self, files=None, progress_callback=None, **kwargs):
        super(FileRequest, self).__init__(**kwargs)
        self.files = files
        self.progress_callback = progress_callback

    @property
    def _request_params(self):
        params = super(FileRequest, self)._request_params

        data = self.files or {}
        data["json"] = ("json", json.dumps(self.data), "application/json")

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
            message = ("{0}\nConsider using pagination for large queries."
                       .format(response.reason))
            # We can't raise-from because of EPEL7
            # pylint: disable=raise-missing-from
            raise CoprTimeoutException(message, response=response)

        raise CoprRequestException("Request is not in JSON format, there is probably a bug in the API code.",
                                   response=response)
