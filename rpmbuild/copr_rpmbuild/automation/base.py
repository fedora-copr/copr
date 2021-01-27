"""
Base class for optionally running tools after builds
"""

class AutomationTool:
    """
    Base class for optionally running tools after builds - mainly static
    analysis tools such as `rpmlint`, `fedora-review`, `covscan`, `rpmgrill`,
    etc. Each of these should be implemented as a separate class providing this
    interface.
    """

    def __init__(self, task, resultdir, mock_config_file, log):
        self.task = task
        self.resultdir = resultdir
        self.mock_config_file = mock_config_file
        self.log = log
        self.package_name = task["package_name"]
        self.chroot = task["chroot"]

    @property
    def enabled(self):
        """
        Do we want to run this tool for this particular task?
        """
        raise NotImplementedError

    def run(self):
        """
        Run this tool and produce some output into `resultdir`
        """
        raise NotImplementedError
