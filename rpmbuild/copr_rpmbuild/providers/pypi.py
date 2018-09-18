import logging
from ..helpers import run_cmd
from .base import Provider

log = logging.getLogger("__main__")


class PyPIProvider(Provider):
    def __init__(self, source_json, outdir, config=None):
        super(PyPIProvider, self).__init__(source_json, outdir, config)
        self.pypi_package_version = source_json["pypi_package_version"]
        self.pypi_package_name = source_json["pypi_package_name"]
        self.spec_template = source_json.get("spec_template", '')
        self.python_versions = source_json["python_versions"] or []

    def tool_presence_check(self):
        try:
            run_cmd(["which", "pyp2rpm"])
        except RuntimeError as err:
            log.error("Please, install pyp2rpm.")
            raise err

    def produce_srpm(self):
        self.tool_presence_check()

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
