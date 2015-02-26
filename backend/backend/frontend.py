import json
from requests import post, RequestException
import time


class FrontendClient(object):
    """
    Object to send data back to fronted
    """

    def __init__(self, opts, events):
        super(FrontendClient, self).__init__()
        self.frontend_url = opts.frontend_url
        self.frontend_auth = opts.frontend_auth

        self.msg = None

    def _post_to_frontend(self, data, url_path):
        """
        Make a request to the frontend
        """

        headers = {"content-type": "application/json"}
        url = "{0}/{1}/".format(self.frontend_url, url_path)
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

    def _post_to_frontend_repeatedly(self, data, url_path, max_repeats=10):
        """
        Make a request max_repeats-time to the frontend
        """
        for i in range(max_repeats):
            try:
                return self._post_to_frontend(data, url_path)
            except RequestException:
                time.sleep(5)
        else:
            raise RequestException("Failed to post to frontend for {} times".format(max_repeats))

    def update(self, data):
        """
        Send data to be updated in the frontend
        """
        self._post_to_frontend_repeatedly(data, "update")

    def starting_build(self, build_id, chroot_name):
        """
        Announce to the frontend that a build is starting.
        Return: True if the build can start
                False if the build can not start (can be cancelled or deleted)
        """
        data = {"build_id": build_id, "chroot": chroot_name}
        response = self._post_to_frontend_repeatedly(data, "starting_build")
        if "can_start" not in response.json():
            raise RequestException("Bad respond from the frontend")
        return response.json()["can_start"]

    def reschedule_build(self, build_id, chroot_name):
        """
        Announce to the frontend that a build should be rescheduled (set pending state).
        """
        data = {"build_id": build_id, "chroot": chroot_name}
        self._post_to_frontend_repeatedly(data, "reschedule_build_chroot")
