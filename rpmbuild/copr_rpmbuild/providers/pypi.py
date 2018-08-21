import logging
from ..helpers import run_cmd
from .base import Provider

log = logging.getLogger("__main__")


class PyPIProvider(Provider):
    def __init__(self, source_json, outdir, config=None):
        super(PyPIProvider, self).__init__(source_json, outdir, config)
        self.pypi_package_version = source_json["pypi_package_version"]
        self.pypi_package_name = source_json["pypi_package_name"]
        self.spec_template = source_json["spec_template"]
        self.python_versions = source_json["python_versions"] or []

    def produce_srpm(self):
        cmd = ["pyp2rpm", self.pypi_package_name, "-t", self.spec_template,
               "--srpm", "-d", self.outdir]

        for i, python_version in enumerate(self.python_versions):
            if i == 0:
                cmd += ["-b", str(python_version)]
            else:
                cmd += ["-p", str(python_version)]

        if self.pypi_package_version:
            cmd += ["-v", self.pypi_package_version]

        return run_cmd(cmd)
