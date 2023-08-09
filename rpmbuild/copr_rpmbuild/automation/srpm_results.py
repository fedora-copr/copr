"""
Create `results.json` file for SRPM builds
"""

import json
import os

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
        data_json = json.dumps(data, indent=4)
        self.log.info("Package info: %s", data_json)
        path = os.path.join(self.resultdir, "results.json")
        with open(path, "w", encoding="utf-8") as dst:
            dst.write(data_json)

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

            path = locate_srpm(self.resultdir)
            self.log.warning("Querying NEVRA from SRPM header: %s", path)
            hdr = get_rpm_header(path)
            return {key: hdr[key] for key in keys}
