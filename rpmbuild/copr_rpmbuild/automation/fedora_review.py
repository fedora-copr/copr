"""
Optionally run `fedora-review` tool after build

See the `fedora-review` tool:
https://pagure.io/FedoraReview

See the Fedora Review Process
https://fedoraproject.org/wiki/Package_Review_Process
"""

import os
import shutil
from copr_rpmbuild.helpers import run_cmd
from copr_rpmbuild.automation.base import AutomationTool


class FedoraReview(AutomationTool):
    """
    Optionally run `fedora-review` tool after build
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fedora_review_enabled = self.task.get("fedora_review")

    @property
    def enabled(self):
        """
        Do we want to run `fedora-review` tool for this particular task?
        Depends on the project settings and the chroot that we build in.
        """
        return self.chroot.startswith("fedora-") and self.fedora_review_enabled

    def run(self):
        """
        Run `fedora-review` tool inside the `resultdir`
        """
        cmd = [
            "fedora-review", "--no-colors", "--prebuilt", "--rpm-spec",
            "--name", self.package_name,
            "--mock-config", self.mock_config_file,
        ]

        try:
            result = run_cmd(cmd, cwd=self.resultdir)
            self.log.info(result.stdout)
            self._filter_results_directory()
        except RuntimeError as ex:
            self.log.warning("Fedora review failed\nerr:\n%s", ex)
            self.log.warning("The build itself will not be marked "
                             "as failed because of this")

    def _filter_results_directory(self):
        """
        Currently, fedora-review tool doesn't have an option to specify
        a destdir, and produces output to a directory called after the package
        name. We want to rename it to something more straighforward.
        See https://pagure.io/FedoraReview/issue/410

        We also don't want to save all results, only some text files.
        """
        srcdir = os.path.join(self.resultdir, self.package_name)
        dstdir = os.path.join(self.resultdir, "fedora-review")
        os.makedirs(dstdir, exist_ok=True)
        results = ["review.txt", "licensecheck.txt", "rpmlint.txt", "files.dir"]
        for result in results:
            try:
                os.rename(os.path.join(srcdir, result),
                          os.path.join(dstdir, result))
            except FileNotFoundError:
                pass
        shutil.rmtree(srcdir)
        print("Moving the results into `fedora-review' directory.")
        print("Review template in: {}".format(os.path.join(dstdir, results[0])))
