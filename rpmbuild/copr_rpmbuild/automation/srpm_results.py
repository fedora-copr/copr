"""
Create `results.json` file for SRPM builds
"""

import os
import simplejson
from copr_rpmbuild.automation.base import AutomationTool
from copr_rpmbuild.helpers import locate_srpm, get_rpm_header


class SRPMResults(AutomationTool):
    """
    Create `results.json` for SRPM builds
    """

    @property
    def enabled(self):
        """
        Do this for every RPM build
        """
        return not self.chroot

    def run(self):
        """
        Create `results.json`
        """
        data = self.get_package_info()
        path = os.path.join(self.resultdir, "results.json")
        with open(path, "w", encoding="utf-8") as dst:
            simplejson.dump(data, dst, indent=4)

    def get_package_info(self):
        """
        Return ``dict`` with interesting package metadata
        """
        srpm = locate_srpm(self.resultdir)
        hdr = get_rpm_header(srpm)
        keys = ["name", "exclusivearch", "excludearch"]
        return {key: hdr[key] for key in keys}
