"""
Create `results.json` file for SRPM builds
"""

import json
import os

from copr_rpmbuild.automation.base import AutomationTool
from copr_rpmbuild.extract_specfile_tags import get_architecture_specific_tags
from copr_rpmbuild.helpers import (
    get_rpm_header,
    macros_for_task,
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
        Do this for every SRPM build
        """
        return self.task["source_type"] is not None

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

    @property
    def target_distros(self):
        """
        Get the list of distributions we build this package against.
        """
        # Handle distributions_in_build first to optimize a bit; the
        # distributions_in_build is a subset of distributions_in_project
        # and if available - we can avoid some macro expansion cycles.
        for field_name in ["distributions_in_build",
                           "distributions_in_project"]:
            if self.task[field_name]:
                self.log.info("Using %s for this build.", field_name)
                return self.task[field_name]
        raise RuntimeError("Running against too old copr-frontend")

    def get_package_info(self):
        """
        Return ``dict`` with interesting package metadata
        """
        output_tags = {}

        # While this is highly inconvenient, many packages still use %lua to
        # define these fields, and Copr must be able to build them.  Unlike
        # other "rpm parsing" use-cases, this does not pose a security risk; we
        # run this script on an disposable worker, so there are no serious
        # consequences if a user "bricks" the machine.
        #
        # Although these fields may expand into target-specific values in
        # theory, we need a single NEVRA for single build.  Consequently,
        # we do not perform separate expansions for each individual target
        # distribution.  Note these fields are not critical for the overall
        # build process, we store some metadata about the build sing these.
        #
        # To fully resolve the issue #1315, we have to fix the
        # backend → distgit protocol, and upload the right srpm.  Or even
        # better, upload all possible src.rpm variants.
        rpm_tags = ["name", "epoch", "version", "release"]

        # These are a bit more important, since these are used to decide which
        # BuildChroots are going to be skipped or not.  And we need to extract
        # them for each target distribution version separately.
        norpm_tags = ["exclusivearch", "excludearch", "buildarch"]

        specfile_path = locate_spec(self.resultdir)

        # TODO: host override_database= on backend and configure
        output_tags["architecture_specific_tags"] = get_architecture_specific_tags(
            specfile_path,
            norpm_tags,
            self.target_distros,
            self.config.get(
                "main", "macro_override_db_url", fallback=(
                    "https://raw.githubusercontent.com/praiskup/"
                    "norpm-macro-overrides/refs/heads/main/distro-arch-specific.json"
                )
            ),
            log=self.log,
        )

        try:
            macros = macros_for_task(self.task, self.config)
            spec = Spec(specfile_path, macros)
            output_tags.update({key: getattr(spec, key) for key in rpm_tags})

        except Exception:  # pylint: disable=broad-exception-caught
            # Specfile library raises too many exception to name the
            # in except block
            msg = "Exception appeared during handling spec file: {0}".format(specfile_path)
            self.log.exception(msg)

            path = locate_srpm(self.resultdir)
            self.log.warning("Querying NEVRA from SRPM header: %s", path)
            hdr = get_rpm_header(path)
            output_tags.update({key: hdr[key] for key in rpm_tags})

        return output_tags
