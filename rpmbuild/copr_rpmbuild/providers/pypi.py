import os
import logging
from ..helpers import run_cmd
from .base import Provider

log = logging.getLogger("__main__")


class PyPIProvider(Provider):
    def init_provider(self):
        source_json = self.source_dict
        self.pypi_package_version = source_json["pypi_package_version"]
        self.pypi_package_name = source_json["pypi_package_name"]
        self.spec_generator = source_json.get("spec_generator", "pyp2rpm")
        self.spec_template = source_json.get("spec_template", '')
        self.python_versions = source_json["python_versions"] or []

    def tool_presence_check(self):
        if self.spec_generator not in ["pyp2rpm", "pyp2spec"]:
            msg = "Unsupported tool: {0}".format(self.spec_generator)
            raise RuntimeError(msg)

        try:
            run_cmd(["which", self.spec_generator])
        except RuntimeError as err:
            log.error("Please, install `%s'.", self.spec_generator)
            raise err

    def produce_srpm(self):
        self.tool_presence_check()

        if self.spec_generator == "pyp2rpm":
            self._produce_srpm_pyp2rpm()
        else:
            self._produce_srpm_pyp2spec()

    def _produce_srpm_pyp2rpm(self):
        cmd = ["pyp2rpm", self.pypi_package_name, "-t", self.spec_template,
               "--srpm", "-d", self.resultdir]

        for i, python_version in enumerate(self.python_versions):
            if i == 0:
                cmd += ["-b", str(python_version)]
            else:
                cmd += ["-p", str(python_version)]

        if self.pypi_package_version:
            cmd += ["-v", self.pypi_package_version]

        return run_cmd(cmd)

    def _produce_srpm_pyp2spec(self):
        os.chdir(self.resultdir)

        cmd = [
            "pyp2spec",
            self.pypi_package_name,
            "--fedora-compliant",
            "--top-level",
        ]
        if self.pypi_package_version:
            cmd += ["-v", self.pypi_package_version]

        try:
            run_cmd(cmd)
        except RuntimeError as err:
            log.error("Unable to generate spec for `%s'",
                      self.pypi_package_name)
            raise err

        spec = "python-{0}.spec".format(self.pypi_package_name)
        spec = os.path.join(self.resultdir, spec)
        self.build_srpm_from_spec(spec)
