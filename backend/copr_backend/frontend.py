import json
import time
import logging
from requests import get, post, put, RequestException

from copr_backend.exceptions import FrontendClientException

# prolong the sleep time before asking frontend again
SLEEP_INCREMENT_TIME = 5
# reasonable timeout for requests that block backend daemon
BACKEND_TIMEOUT = 2*60

class FrontendClientRetryError(Exception):
    pass


class FrontendClient(object):
    """
    Object to send data back to fronted
    """

    # do we block the main daemon process?
    try_indefinitely = False

    def __init__(self, opts, logger=None, try_indefinitely=False):
        self.frontend_url = "{}/backend".format(opts.frontend_base_url)
        self.frontend_auth = opts.frontend_auth
        self.try_indefinitely = try_indefinitely

        self.msg = None
        self.logger = logger

    @property
    def log(self):
        'return configured logger object, or no-op logger'
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.addHandler(logging.NullHandler())
        return self.logger

    def _frontend_request(self, url_path, data=None, authenticate=True,
                          method='post'):
        headers = {"content-type": "application/json"}
        url = "{}/{}/".format(self.frontend_url, url_path)
        auth = ("user", self.frontend_auth) if authenticate else None

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
            raise FrontendClientRetryError(
                "Requests error on {}: {}".format(url, str(ex)))

        if response.status_code >= 500:
            # Server error.  Hopefully this is only temporary problem, we wan't
            # to re-try, and wait till the server works again.
            raise FrontendClientRetryError(
                "Request server error on {}: {} {}".format(
                    url, response.status_code, response.reason))

        if response.status_code >= 400:
            # Client error.  The mistake is on our side, it doesn't make sense
            # to continue with retries.
            raise FrontendClientException(
                "Request client error on {}: {} {}".format(
                    url, response.status_code, response.reason))

        # TODO: Success, but tighten the redirects etc.
        return response

    def _frontend_request_repeatedly(self, url_path, method='post', data=None,
                                     authenticate=True):
        """
        Repeat the request until it succeeds, or timeout is reached.
        """
        sleep = SLEEP_INCREMENT_TIME
        start = time.time()
        stop = start + BACKEND_TIMEOUT

        i = 0
        while True:
            i += 1
            if not self.try_indefinitely and time.time() > stop:
                raise FrontendClientException(
                    "Attempt to talk to frontend timeouted "
                    "(we gave it {} attempts)".format(i))

            try:
                return self._frontend_request(url_path, data=data,
                                              authenticate=authenticate,
                                              method=method)
            except FrontendClientRetryError as ex:
                self.log.warning("Retry request #%s on %s: %s", i, url_path,
                                 str(ex))
                time.sleep(sleep)
                sleep += SLEEP_INCREMENT_TIME


    def _post_to_frontend_repeatedly(self, data, url_path):
        """
        Repeat the request until it succeeds, or timeout is reached.
        """
        return self._frontend_request_repeatedly(url_path, data=data)

    def get(self, url_path):
        'Issue relentless GET request to Frontend'
        return self._frontend_request_repeatedly(url_path, method='get')

    def post(self, url_path, data):
        'Issue relentless POST request to Frontend'
        return self._frontend_request_repeatedly(url_path, data=data)

    def put(self, url_path, data):
        'Issue relentless POST request to Frontend'
        return self._frontend_request_repeatedly(url_path, data=data,
                                                 method='put')

    def update(self, data):
        """
        Send data to be updated in the frontend
        """
        self._post_to_frontend_repeatedly(data, "update")

    def starting_build(self, data):
        """
        Announce to the frontend that a build is starting.

        :return: True if the build can start or False if the build can not start (can be cancelled or deleted).
        """
        response = self._post_to_frontend_repeatedly(data, "starting_build")
        if "can_start" not in response.json():
            raise FrontendClientException("Bad response from the frontend")
        return response.json()["can_start"]

    def reschedule_build(self, build_id, task_id, chroot_name):
        """
        Announce to the frontend that a build should be rescheduled (set pending state).
        """
        data = {"build_id": build_id, "task_id": task_id, "chroot": chroot_name}
        self._post_to_frontend_repeatedly(data, "reschedule_build_chroot")

    def reschedule_all_running(self):
        response = self._post_to_frontend_repeatedly({}, "reschedule_all_running")
        if response.status_code != 200:
            raise FrontendClientException("Failed to reschedule builds")
