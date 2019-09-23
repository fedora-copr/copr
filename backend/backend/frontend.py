import json
import time
import logging
from requests import post, get, RequestException

RETRY_TIMEOUT = 5

class FrontendClient(object):
    """
    Object to send data back to fronted
    """

    def __init__(self, opts, logger=None):
        super(FrontendClient, self).__init__()
        self.frontend_url = "{}/backend".format(opts.frontend_base_url)
        self.frontend_auth = opts.frontend_auth

        self.msg = None
        self.logger = logger

    @property
    def log(self):
        'return configured logger object, or no-op logger'
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.addHandler(logging.NullHandler())
        return self.logger


    def _post_to_frontend(self, data, url_path):
        """
        Make a request to the frontend
        """

        headers = {"content-type": "application/json"}
        url = "{}/{}/".format(self.frontend_url, url_path)
        auth = ("user", self.frontend_auth)

        self.msg = None

        try:
            response = post(url, data=json.dumps(data), auth=auth, headers=headers)
            if response.status_code >= 400:
                self.msg = "Failed to submit to frontend: {0}: {1}".format(
                    response.status_code, response.text)
                raise RequestException(self.msg)
        except RequestException as e:
            self.msg = "Post request failed: {0}".format(e)
            raise
        return response

    def get_reliably(self, url_path):
        """
        Get the URL response from frontend, try indefinitely till the server
        gives us answer.
        """
        url = "{}/{}/".format(self.frontend_url, url_path)
        auth = ("user", self.frontend_auth)

        attempt = 0
        while True:
            attempt += 1
            try:
                response = get(url, auth=auth)
            except RequestException as ex:
                self.msg = "Get request {} failed: {}".format(attempt, ex)
                time.sleep(RETRY_TIMEOUT)
                continue

            return response


    def _post_to_frontend_repeatedly(self, data, url_path, max_repeats=10):
        """
        Make a request max_repeats-time to the frontend
        """
        for i in range(max_repeats):
            try:
                return self._post_to_frontend(data, url_path)
            except RequestException:
                self.log.warning("failed to post data to frontend, attempt #{0}".format(i))
                time.sleep(5)
        else:
            raise RequestException("Failed to post to frontend for {} times".format(max_repeats))

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
            raise RequestException("Bad respond from the frontend")
        return response.json()["can_start"]

    def reschedule_build(self, build_id, task_id, chroot_name):
        """
        Announce to the frontend that a build should be rescheduled (set pending state).
        """
        data = {"build_id": build_id, "task_id": task_id, "chroot": chroot_name}
        self._post_to_frontend_repeatedly(data, "reschedule_build_chroot")

    def reschedule_all_running(self, attempts):
        response = self._post_to_frontend_repeatedly({}, "reschedule_all_running", attempts)
        if response.status_code != 200:
            raise RequestException("Failed to reschedule all running jobs")
