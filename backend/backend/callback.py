import json
import requests
import time


class FrontendCallback(object):
    """
    Object to send data back to fronted
    """

    def __init__(self, opts, events):
        super(FrontendCallback, self).__init__()
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
            response = requests.post(url, data=json.dumps(data), auth=auth,
                                     headers=headers)
            if response.status_code != 200:
                self.msg = "Failed to submit to frontend: {0}: {1}".format(
                    response.status_code, response.text)
                raise requests.RequestException(self.msg)
        except requests.RequestException as e:
            self.msg = "Post request failed: {0}".format(e)
            raise
        return response

    def _post_to_frontend_repeatedly(self, data, url_path, max_repeats=10):
        """
        Make a request max_repeats-time to the frontend
        """
        repeats = 0
        while repeats <= max_repeats:
            try:
                response = self._post_to_frontend(data, url_path)
                break
            except requests.RequestException:

                if repeats == max_repeats:
                    raise
                repeats += 1
                time.sleep(5)
        return response

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
            raise requests.RequestException("Bad respond from the frontend")
        return response.json()["can_start"]
