import logging

from copr_common.request import SafeRequest, RequestError
from copr_backend.exceptions import FrontendClientException


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

    def get(self, url_path):
        'Issue relentless GET request to Frontend'
        return self.send(url_path, method='get')

    def post(self, url_path, data):
        'Issue relentless POST request to Frontend'
        return self.send(url_path, data=data)

    def put(self, url_path, data):
        'Issue relentless POST request to Frontend'
        return self.send(url_path, data=data, method='put')

    def send(self, url_path, method='post', data=None, authenticate=True):
        # """
        # Repeat the request until it succeeds, or timeout is reached.
        # """
        url = "{}/{}/".format(self.frontend_url, url_path)
        auth = self.frontend_auth if authenticate else None

        try:
            request = SafeRequest(auth=auth, log=self.log,
                                  try_indefinitely=self.try_indefinitely)
            response = request.send(url, method=method, data=data)
            return response
        except RequestError as ex:
            raise FrontendClientException(ex)

    def update(self, data):
        """
        Send data to be updated in the frontend
        """
        self.post("update", data)

    def starting_build(self, data):
        """
        Announce to the frontend that a build is starting.

        :return: True if the build can start or False if the build can not start (can be cancelled or deleted).
        """
        response = self.post("starting_build", data)
        if "can_start" not in response.json():
            raise FrontendClientException("Bad response from the frontend")
        return response.json()["can_start"]

    def reschedule_build(self, build_id, task_id, chroot_name):
        """
        Announce to the frontend that a build should be rescheduled (set pending state).
        """
        data = {"build_id": build_id, "task_id": task_id, "chroot": chroot_name}
        self.post("reschedule_build_chroot", data)
