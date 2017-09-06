import os
import logging
import requests
from ..helpers import run_cmd
from .base import Provider


log = logging.getLogger("__main__")


class SpecUrlProvider(Provider):
    def __init__(self, source_json, workdir=None, confdirs=None):
        super(SpecUrlProvider, self).__init__(source_json, workdir, confdirs)
        self.url = source_json["url"]

    def run(self):
        if not self.url.endswith(".spec"):
            raise RuntimeError("Not a path to .spec file")
        self.save_spec()
        self.touch_sources()
        self.produce_srpm()

    def save_spec(self):
        response = requests.get(self.url)
        path = os.path.join(self.workdir, self.url.split("/")[-1])
        with open(path, "w") as spec:
            spec.write(response.text)

    def produce_srpm(self):
        cmd = ["rpkg", "srpm"]
        return run_cmd(cmd, cwd=self.workdir)
