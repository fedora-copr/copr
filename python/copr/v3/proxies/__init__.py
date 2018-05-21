import os


class BaseProxy(object):
    def __init__(self, config):
        self.config = config

    @property
    def api_base_url(self):
        return os.path.join(self.config["copr_url"], "api_3", "")

    @property
    def auth(self):
        return self.config["login"], self.config["token"]
