# copr error/exceptions
class CoprBackendError(Exception):

    def __init__(self, msg):
        super(CoprBackendError, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg

class CoprWorkerError(CoprBackendError):
    pass

