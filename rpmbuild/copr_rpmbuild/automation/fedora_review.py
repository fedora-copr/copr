"""
Optionally run `fedora-review` tool after build

See the `fedora-review` tool:
https://pagure.io/FedoraReview

See the Fedora Review Process
https://fedoraproject.org/wiki/Package_Review_Process
"""

import os
import shutil
from contextlib import contextmanager
from typing import Generator

from copr_rpmbuild.helpers import run_cmd
from copr_rpmbuild.automation.base import AutomationTool


@contextmanager
def cache_directory(resultdir) -> Generator[str, None, None]:
    """
    Create a directory for a job to use as the XDG cache.

    :param str resultdir: Parent directory for the run results
    :return: Path to cache directory
    """
    cachedir = os.path.join(resultdir, "cache")
    try:
        os.makedirs(cachedir, exist_ok=True)
        yield cachedir
    finally:
        shutil.rmtree(cachedir)


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
        if not self.chroot:
            return False
        if not self.chroot.startswith("fedora-"):
            return False
        return self.fedora_review_enabled

    def run(self):
        """
        Run `fedora-review` tool inside the `resultdir`
        """
        cmd = [
            "fedora-review", "--no-colors", "--prebuilt", "--rpm-spec",
            "--name", self.package_name,
            "--mock-config", self.mock_config_file,
        ]
        with cache_directory(self.resultdir) as cachedir:
            try:
                result = run_cmd(cmd, cwd=self.resultdir, env={"XDG_CACHE_HOME": cachedir})
                self.log.info(result.stdout)
            except RuntimeError as ex:
                self.log.warning("Fedora review failed\nerr:\n%s", ex)
                self.log.warning("The build itself will not be marked "
                                 "as failed because of this")
            self._filter_results_directory(cachedir)

    def _filter_results_directory(self, cachedir: str):
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

        logfile = os.path.join(cachedir, "fedora-review.log")

        # The fedora-review command failed to start so badly that it didn't even create a log file.
        # Given how early that should happen, this merits investigation.
        if not os.path.exists(logfile):
            self.log.error("Can't find fedora-review log: %s", logfile)
            self.log.error("Please raise a bug on https://github.com/fedora-copr/copr including a link to this build")
            # If the log file doesn't exist, there's zero chance the results exist
            return

        os.rename(logfile, os.path.join(dstdir, "fedora-review.log"))

        # The fedora-review command failed so early that it didn't even create
        # the resultdir. Nothing to do here.
        if not os.path.exists(srcdir):
            self.log.error("Can't find fedora-review results: %s", srcdir)
            return

        results = ["review.txt", "review.json", "licensecheck.txt",
                   "rpmlint.txt", "files.dir", "diff.txt"]
        for result in results:
            try:
                os.rename(os.path.join(srcdir, result),
                          os.path.join(dstdir, result))
            except FileNotFoundError:
                pass
        shutil.rmtree(srcdir)
        self.log.info("Moving the results into `fedora-review' directory.")
        self.log.info("Review template in: %s", os.path.join(dstdir, results[0]))
