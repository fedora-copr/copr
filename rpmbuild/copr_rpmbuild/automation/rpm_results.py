"""
Create `results.json` file
"""

import json
import os

from copr_rpmbuild.automation.base import AutomationTool
from copr_rpmbuild.helpers import get_rpm_header


class RPMResults(AutomationTool):
    """
    Create `results.json` file containing NEVRAs for all built RPM files
    """

    @property
    def enabled(self):
        """
        Do this for every RPM build
        """
        return self.task["source_type"] is None

    def run(self):
        """
        Create `results.json`
        """
        nevras = self.find_results_nevras_dicts()
        packages = {"packages": nevras}
        packages_json = json.dumps(packages, indent=4)
        self.log.info("Package info:\n%s", packages_json)
        path = os.path.join(self.resultdir, "results.json")
        with open(path, "w", encoding="utf-8") as dst:
            dst.write(packages_json)

    def find_results_nevras_dicts(self):
        """
        Find all RPM packages in the `resultdir` and return their NEVRAs
        as `dicts`
        """
        nevras = []
        for entry in os.scandir(self.resultdir):
            result = entry.name
            if not result.endswith(".rpm"):
                continue
            package = os.path.join(self.resultdir, result)
            nevras.append(self.get_nevra_dict(package))
        return nevras

    @classmethod
    def get_nevra_dict(cls, path):
        """
        Takes a package path and returns its NEVRA as a `dict`
        """
        filename = os.path.basename(path)
        if not filename.endswith(".rpm"):
            msg = "File name doesn't end with '.rpm': {}".format(path)
            raise ValueError(msg)

        hdr = get_rpm_header(path)
        arch = "src" if filename.endswith(".src.rpm") else hdr["arch"]
        return {
            "name": hdr["name"],
            "epoch": hdr["epoch"],
            "version": hdr["version"],
            "release": hdr["release"],
            "arch": arch,
        }
