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
        self.create_rpmmacros()
        self.touch_sources()

        # Change home directory to workdir, so .rpmmacros file will be read from there
        os.environ["HOME"] = self.workdir
        self.produce_srpm()

    def touch_sources(self):
        # Create an empty sources file to get rid of
        # "sources file doesn't exist. Source files download skipped."
        path = os.path.join(self.workdir, "sources")
        open(path, "w").close()

    def save_spec(self):
        response = requests.get(self.url)
        path = os.path.join(self.workdir, self.url.split("/")[-1])
        with open(path, "w") as spec:
            spec.write(response.text)

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            rpmmacros.write("%_disable_source_fetch 0")

    def produce_srpm(self):
        cmd = ["rpkg", "srpm"]
        return run_cmd(cmd, cwd=self.workdir)
