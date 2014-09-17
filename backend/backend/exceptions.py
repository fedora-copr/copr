class MockRemoteError(Exception):
    def __init__(self, msg):
        super(MockRemoteError, self).__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg


class BuilderError(MockRemoteError):
    pass


class CoprSignError(MockRemoteError):
    """
    Related to invocation of /bin/sign

    has additional  fields:
    :ivar cmd: command which was executed
    :ivar stdout: message content
    :ivar stderr: error message
    """

    def __init__(self, msg, cmd=None, stdout=None, stderr=None,
                 return_code=None):

        super(CoprSignError, self).__init__(msg)
        self.cmd = cmd
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        out = super(CoprSignError, self).__str__()
        if self.cmd:
            out += ("\n"
                    "return code {} after invocation of: {} \n"
                    "stderr: {}\n"
                    "stdout: {}\n").format(
                        self.return_code, self.cmd, self.stdout, self.stderr)
        return out


class CoprSignNoKeyError(CoprSignError):
    pass


class CoprKeygenRequestError(MockRemoteError):
    """
    Errors during request to copr-keygen service

    has additional  fields:
    :ivar request: tuple of parameters for request.request
    :ivar response: requests.Response
    """

    def __init__(self, msg, request=None, response=None):
        super(CoprKeygenRequestError, self).__init__(msg)
        self.request = request
        self.response = response

    def __str__(self):
        out = super(CoprKeygenRequestError, self).__str__()
        out += "\nrequest to copr-keygen: {0}\n".format(self.request)
        if self.response:
            out += "status code: {1}\n" "response content: {2}\n" \
                .format(self.response.status_code, self.response.content)
        return out


class CoprBackendError(Exception):
    def __init__(self, msg):
        super(CoprBackendError, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg


class CoprWorkerError(CoprBackendError):
    pass


