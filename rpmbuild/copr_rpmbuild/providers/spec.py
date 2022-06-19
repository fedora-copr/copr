import os
import logging

from six.moves.urllib.parse import urlparse

from copr_rpmbuild.providers.base import Provider

log = logging.getLogger("__main__")


class UrlProvider(Provider):
    def init_provider(self):
        self.url = self.source_dict["url"]
        self.parsed_url = urlparse(self.url)

    def save_spec(self):
        response = self.request.get(self.url)
        path = os.path.join(self.workdir, self.parsed_url.path.split("/")[-1])
        with open(path, "w") as spec:
            spec.write(response.text)
        return path

    def download_srpm(self):
        basename = os.path.basename(self.parsed_url.path)
        filename = os.path.join(self.resultdir, basename)
        response = self.request.get(self.url, stream=True)
        if response.status_code != 200:
            raise RuntimeError('Requests get status "{0}" for "{1}"'.format(
                response.status_code, self.url
            ))

        with open(filename, 'wb') as f:
            for chunk in response:
                f.write(chunk)

    def produce_srpm(self):
        if self.parsed_url.path.endswith(".spec"):
            spec_path = self.save_spec()
            return self.build_srpm_from_spec(spec_path)
        if self.parsed_url.path.endswith(".src.rpm"):
            return self.download_srpm()
        raise RuntimeError("Url is not a path to .spec nor .src.rpm file")
