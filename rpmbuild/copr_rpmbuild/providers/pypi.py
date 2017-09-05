import logging
from ..helpers import run_cmd


log = logging.getLogger("__main__")


class PyPIProvider(object):
    def __init__(self, source_json, workdir=None, confdirs=None):
        self.workdir = workdir
        self.confdirs = confdirs
        self.pypi_package_version = source_json["pypi_package_version"]
        self.pypi_package_name = source_json["pypi_package_name"]
        self.python_versions = source_json["python_versions"] or []

    def run(self):
        self.produce_srpm()

    def produce_srpm(self):
        cmd = ["pyp2rpm", self.pypi_package_name, "--srpm", "-d", self.workdir]

        for i, python_version in enumerate(self.python_versions):
            if i == 0:
                cmd += ["-b", str(python_version)]
            else:
                cmd += ["-p", str(python_version)]

        if self.pypi_package_version:
            cmd += ["-v", self.pypi_package_version]

        return run_cmd(cmd)