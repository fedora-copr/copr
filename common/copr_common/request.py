"""
Common Copr code for dealing with HTTP requests
"""

import json
import time
from requests import get, post, put, RequestException


class SafeRequest:
    """
    Build a HTTP request and _safely_ send it.

    If the server cannot be reached, the request is repeated either indefinitely
    or until a timeout is reached.
    """

    # Prolong the sleep time before asking frontend again
    SLEEP_INCREMENT_TIME = 5

    # Reasonable timeout for requests that block the client
    TIMEOUT = 2*60

    def __init__(self, auth=None, log=None, try_indefinitely=False):
        self.auth = auth
        self.log = log
        self.try_indefinitely = try_indefinitely

    def get(self, url):
        """
        Issue relentless GET request to a given URL
        """
        return self.send(url, method='get')

    def post(self, url, data):
        """
        Issue relentless POST request to given URL
        """
        return self.send(url, method='post', data=data)

    def put(self, url, data):
        """
        Issue relentless POST request to a given URL
        """
        return self.send(url, method='put', data=data)

    def send(self, url, method, data=None):
        """
        Issue relentless request to a given URL
        """
        return self._send_request_repeatedly(url, method=method, data=data)

    def _send_request(self, url, method, data=None):
        headers = {"content-type": "application/json"}
        auth = ("user", self.auth) if self.auth else None

        try:
            kwargs = {
                'auth': auth,
                'headers': headers,
            }
            method = method.lower()
            if method in ['post', 'put']:
                kwargs['data'] = json.dumps(data)
                method = post if method == 'post' else put
            else:
                method = get
            response = method(url, **kwargs)
        except RequestException as ex:
            raise RequestRetryError(
                "Requests error on {}: {}".format(url, str(ex)))

        if response.status_code >= 500:
            # Server error.  Hopefully this is only temporary problem, we wan't
            # to re-try, and wait till the server works again.
            raise RequestRetryError(
                "Request server error on {}: {} {}".format(
                    url, response.status_code, response.reason))

        if response.status_code >= 400:
            # Client error.  The mistake is on our side, it doesn't make sense
            # to continue with retries.
            raise RequestError(
                "Request client error on {}: {} {}".format(
                    url, response.status_code, response.reason))

        # TODO: Success, but tighten the redirects etc.
        return response

    def _send_request_repeatedly(self, url, method, data=None):
        """
        Repeat the request until it succeeds, or timeout is reached.
        """
        sleep = self.SLEEP_INCREMENT_TIME
        start = time.time()
        stop = start + self.TIMEOUT

        i = 0
        while True:
            i += 1
            if not self.try_indefinitely and time.time() > stop:
                raise RequestError(
                    "Attempt to talk to server timeouted "
                    "(we gave it {} attempts)".format(i))

            try:
                return self._send_request(url, method=method, data=data)
            except RequestRetryError as ex:
                self.log.warning("Retry request #%s on %s: %s", i, url,
                                 str(ex))
                time.sleep(sleep)
                sleep += self.SLEEP_INCREMENT_TIME


class RequestRetryError(Exception):
    """
    Request to server failed, try again
    """


class RequestError(Exception):
    """
    Request to server failed
    """
