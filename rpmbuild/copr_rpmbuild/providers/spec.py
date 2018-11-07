import os
import logging
import requests
from ..helpers import run_cmd
from .base import Provider

log = logging.getLogger("__main__")


class UrlProvider(Provider):
    def __init__(self, source_json, outdir, config=None):
        super(UrlProvider, self).__init__(source_json, outdir, config)
        self.url = source_json["url"]

    def save_spec(self):
        response = requests.get(self.url)
        path = os.path.join(self.workdir, self.url.split("/")[-1])
        with open(path, "w") as spec:
            spec.write(response.text)
        return path

    def build_srpm_from_spec(self):
        spec_path = self.save_spec()
        cmd = ["rpkg", "srpm", "--outdir", self.outdir, '--spec', spec_path]
        return run_cmd(cmd, cwd=self.workdir)

    def download_srpm(self):
        basename = os.path.basename(self.url)
        filename = os.path.join(self.outdir, basename)
        response = requests.get(self.url, stream=True)
        if response.status_code != 200:
            raise RuntimeError('Requests get status "{0}" for "{1}"'.format(
                response.status_code, self.url
            ))

        with open(filename, 'wb') as f:
            for chunk in response:
                f.write(chunk)

    def produce_srpm(self):
        if self.url.endswith(".spec"):
            return self.build_srpm_from_spec()
        if self.url.endswith(".src.rpm"):
            return self.download_srpm()
        raise RuntimeError("Url is not a path to .spec nor .src.rpm file")
