"""
Create `results.json` file for SRPM builds
"""

import os
import simplejson
from copr_rpmbuild.automation.base import AutomationTool
from copr_rpmbuild.helpers import (
    get_rpm_header,
    locate_srpm,
    locate_spec,
    Spec,
)


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
        keys = ["name", "epoch", "version", "release",
                "exclusivearch", "excludearch"]
        try:
            path = locate_spec(self.resultdir)
            spec = Spec(path)
            return {key: getattr(spec, key) for key in keys}

        except Exception:  # pylint: disable=broad-exception-caught
            # Specfile library raises too many exception to name the
            # in except block
            msg = "Exception appeared during handling spec file: {0}".format(path)
            self.log.exception(msg)

            # Fallback to querying NEVRA from the SRPM package header
            path = locate_srpm(self.resultdir)
            hdr = get_rpm_header(path)
            return {key: hdr[key] for key in keys}
