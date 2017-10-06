import os
import logging
import requests
from ..helpers import run_cmd
from .base import Provider

log = logging.getLogger("__main__")


class SpecUrlProvider(Provider):
    def __init__(self, source_json, outdir, config=None):
        super(SpecUrlProvider, self).__init__(source_json, outdir, config)
        self.url = source_json["url"]

    def save_spec(self):
        response = requests.get(self.url)
        path = os.path.join(self.workdir, self.url.split("/")[-1])
        with open(path, "w") as spec:
            spec.write(response.text)
        return path

    def produce_srpm(self):
        if not self.url.endswith(".spec"):
            raise RuntimeError("Not a path to .spec file")
        spec_path = self.save_spec()
        cmd = ["rpkg", "srpm", "--outdir", self.outdir, '--spec', spec_path]
        return run_cmd(cmd, cwd=self.workdir)
