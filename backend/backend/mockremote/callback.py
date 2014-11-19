from ..helpers import log


class DefaultCallBack(object):

    def __init__(self, **kwargs):
        self.quiet = kwargs.get("quiet", False)
        self.logfn = kwargs.get("logfn", None)

    def start_build(self, pkg):
        pass

    def end_build(self, pkg):
        pass

    def start_download(self, pkg):
        pass

    def end_download(self, pkg):
        pass

    def error(self, msg):
        self.log("Error: {0}".format(msg))

    def log(self, msg):
        if not self.quiet:
            print(msg)


class CliLogCallBack(DefaultCallBack):

    def __init__(self, **kwargs):
        super(CliLogCallBack, self).__init__(**kwargs)

    def start_build(self, pkg):
        msg = "Start build: {0}".format(pkg)
        self.log(msg)

    def end_build(self, pkg):
        msg = "End Build: {0}".format(pkg)
        self.log(msg)

    def start_download(self, pkg):
        msg = "Start retrieve results for: {0}".format(pkg)
        self.log(msg)

    def end_download(self, pkg):
        msg = "End retrieve results for: {0}".format(pkg)
        self.log(msg)

    def error(self, msg):
        self.log("Error: {0}".format(msg))

    def log(self, msg):
        log(self.logfn, msg, self.quiet)
