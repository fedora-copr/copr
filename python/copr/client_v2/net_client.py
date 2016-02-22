# coding: utf-8
# pylint: disable=W1202
from collections import namedtuple
import json

from logging import getLogger

from requests import request, ConnectionError
from requests_toolbelt.multipart.encoder import MultipartEncoder

from ..util import UnicodeMixin

log = getLogger(__name__)


class RequestError(Exception, UnicodeMixin):
    def __init__(self, msg, url, request_kwargs=None, response=None, request_body=None):
        super(RequestError, self).__init__()
        self.msg = msg
        self.url = url
        self.request_body = request_body
        self.request_kwargs = request_kwargs or dict()
        if "auth" in self.request_kwargs:
            self.request_kwargs["auth"] = "<hidden>"
        self.response = response

    @property
    def response_json(self):
        if self.response is None:
            raise ValueError("No response")
        if self.response.headers["content-type"] == "application/json":
            try:
                result = json.loads(self.response.text)
            except (ValueError, AttributeError):
                raise ValueError(
                    "Malformed response, couldn't "
                    "get json content, raw:\n{0}"
                    .format(self.response.text)
                )

            return result
        else:
            return None

    def __unicode__(self):
        res = "Error occurred while accessing {0}: {1}\n".format(
            self.url, self.msg)
        if self.response is not None:
            res += "code {0}: {1}\n".format(self.response.status_code, self.response_json["message"])
        return res


class NetworkError(RequestError):
    def __init__(self, url, request_kwargs, requests_error):
        self.requests_error = requests_error
        super(NetworkError, self).__init__(
            u"Connection error", url, request_kwargs)

    def __unicode__(self):
        res = super(NetworkError, self).__unicode__()
        res += u"Original error: {0}\n".format(self.requests_error)
        return res


class AuthError(RequestError):
    def __init__(self, url, request_kwargs, response):
        super(AuthError, self).__init__("Authorization failed",
                                        url, request_kwargs, response)


class ResponseWrapper(object):

    def __init__(self, response):
        """
        :raises ValueError: when fails to deserialize json content
        """
        self.response = response
        if response.status_code != 204 and response.content:
            if isinstance(response.content, bytes):
                self.json = json.loads(response.content.decode('utf-8'))
            else:
                self.json = json.loads(response.content)
        else:
            self.json = None

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def headers(self):
        return self.response.headers

MultiPartTuple = namedtuple("MultiPartTuple", ["key", "name", "obj", "content_type"])


class NetClient(object):
    """
    Abstraction around python-requests

    :param str login: login for BasicAuth
    :param str password: password for BasicAuth
    """

    def __init__(self, login=None, password=None):
        self.login = login
        self.token = password

    def request_multipart(self, url, method=None, query_params=None,
                          data_parts=None, do_auth=False):
        """
        :type data_parts: list of MultiPartTuple

        """
        parts = {}
        for key, name, obj, content_type in data_parts:
            parts[key] = (name, obj, content_type)

        data = MultipartEncoder(parts)
        headers = {
            "content-type": data.content_type
        }
        return self.request(url, method=method, query_params=query_params,
                            data=data, do_auth=do_auth, headers=headers)

    def request(self, url, method=None, query_params=None, data=None, do_auth=False, headers=None):
        """
        :param str method: what HTTP method to use, default is GET, allowed methods: GET, POST, PUT, DELETE
        :param dict query_params: HTTP query parameters
        :param str data: serialized data, when present set default content type to application/json
        :param dict headers: dict with headers, takes priority over implicit ones
        :param bool do_auth: sends auth headers when enabled

        :raises: RequestError
        """

        if method is None:
            method = "get"
        elif method.lower() not in ["get", "post", "delete", "put"]:
            raise RequestError("Method {0} not allowed".format(method), url)

        kwargs = {}
        headers = headers or {}
        if do_auth:
            if self.login is None or self.token is None:
                raise RequestError("Credentionals for BasicAuth "
                                   "not set, request aborted",
                                   url, kwargs)
            kwargs["auth"] = (self.login, self.token)
        if query_params:
            kwargs["params"] = query_params
        if data:
            kwargs["data"] = data
            if "content-type" not in headers:
                headers["content-type"] = "application/json"

        try:
            response = request(
                method=method.upper(),
                url=url,
                headers=headers,
                **kwargs
            )
            log.debug("raw response: {0}".format(response.text))
        except ConnectionError as e:
            raise NetworkError(url, kwargs, e)

        if response.status_code == 403:
            raise AuthError(url, kwargs, response)

        if response.status_code >= 500:
            raise RequestError("Server error", url, kwargs, response)

        if response.status_code > 399:
            raise RequestError("Request error", url, kwargs, response)

        try:
            return ResponseWrapper(response)
        except ValueError:
            raise RequestError("Failed to parse server response", url, kwargs, response)

    def get(self, url, query_params=None):
        return self.request(url, query_params=query_params)
