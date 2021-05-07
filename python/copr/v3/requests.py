from __future__ import absolute_import

import os
import json
import requests
import requests_gssapi
from copr.v3.helpers import List
from munch import Munch
from future.utils import raise_from
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from .exceptions import CoprRequestException, CoprNoResultException, CoprTimeoutException, CoprGssapiException


GET = "GET"
POST = "POST"
PUT = "PUT"


class Request(object):
    # This should be a replacement of the _fetch method from APIv1
    # We can have Request, FileRequest, AuthRequest/UnAuthRequest, ...

    def __init__(self, endpoint, api_base_url=None, method=None, data=None, params=None, auth=None):
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
        self.endpoint = endpoint
        self.api_base_url = api_base_url
        self._method = method or GET
        self.data = data
        self.params = params or {}
        self.auth = auth
        self.headers = None

    @property
    def endpoint_url(self):
        endpoint = self.endpoint.strip("/").format(**self.params)
        return os.path.join(self.api_base_url, endpoint)

    @property
    def method(self):
        return self._method.upper()

    def send(self):
        session = requests.Session()
        if not isinstance(self.auth, tuple):
            # api token not available, set session cookie obtained via gssapi
            session.cookies.set("session", self.auth)

        try:
            response = session.request(**self._request_params)
        except requests.exceptions.ConnectionError:
            raise CoprRequestException("Unable to connect to {0}.".format(self.api_base_url))
        except requests_gssapi.exceptions.SPNEGOExchangeError as e:
            raise_from(CoprGssapiException("Kerberos ticket has expired."), e)
        handle_errors(response)
        return response

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
    def __init__(self, endpoint, files=None, progress_callback=None, **kwargs):
        super(FileRequest, self).__init__(endpoint, **kwargs)
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
