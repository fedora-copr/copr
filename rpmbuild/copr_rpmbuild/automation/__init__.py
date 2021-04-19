"""
This package contains support for running (mainly) static analysis tools such as
`rpmlint`, `fedora-review`, `covscan`, `rpmgrill`, etc.
"""

from copr_rpmbuild.automation.fedora_review import FedoraReview
from copr_rpmbuild.automation.rpm_results import RPMResults


def run_automation_tools(task, resultdir, mock_config_file, log):
    """
    Iterate over all supported post-build tools (e.g. `fedora-review`,
    `rpmlint`, etc) and run the desired ones for a given task.
    """
    tools = [FedoraReview, RPMResults]
    for _class in tools:
        tool = _class(task, resultdir, mock_config_file, log)
        if not tool.enabled:
            continue
        log.info("Running %s tool", tool.__class__.__name__)
        tool.run()
