"""
Create `results.json` file
"""

import os
import rpm
import simplejson
from copr_rpmbuild.automation.base import AutomationTool


class RPMResults(AutomationTool):
    """
    Create `results.json` file containing NEVRAs for all built RPM files
    """

    @property
    def enabled(self):
        """
        Do this for every build
        """
        return True

    def run(self):
        """
        Create `results.json`
        """
        nevras = self.find_results_nevras_dicts()
        packages = {"packages": nevras}
        path = os.path.join(self.resultdir, "results.json")
        with open(path, "w") as dst:
            simplejson.dump(packages, dst, indent=4)

    def find_results_nevras_dicts(self):
        """
        Find all RPM packages in the `resultdir` and return their NEVRAs
        as `dicts`
        """
        nevras = []
        for result in os.listdir(self.resultdir):
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

        hdr = cls.get_rpm_header(path)
        arch = "src" if filename.endswith(".src.rpm") else hdr["arch"]
        return {
            "name": hdr["name"],
            "epoch": hdr["epoch"] or 0,
            "version": hdr["version"],
            "release": hdr["release"],
            "arch": arch,
        }

    @staticmethod
    def get_rpm_header(path):
        """
        Examine a RPM package file and return its header
        See docs.fedoraproject.org/en-US/Fedora_Draft_Documentation/0.1/html/RPM_Guide/ch16s04.html
        """
        ts = rpm.TransactionSet()
        with open(path, "r") as f:
            hdr = ts.hdrFromFdno(f.fileno())
            return hdr
