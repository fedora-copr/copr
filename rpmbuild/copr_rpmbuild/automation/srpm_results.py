"""
Create `results.json` file for SRPM builds
"""

import os
import simplejson
from copr_rpmbuild.automation.base import AutomationTool
from copr_rpmbuild.helpers import locate_spec, Spec


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
        spec_path = locate_spec(self.resultdir)
        spec = Spec(spec_path)
        keys = ["name", "exclusivearch", "excludearch"]
        return {key: getattr(spec, key) for key in keys}
