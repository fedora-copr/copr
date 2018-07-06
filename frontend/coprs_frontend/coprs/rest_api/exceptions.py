# coding: utf-8

class ApiError(Exception):
    def __init__(self, code, msg, data=None, **kwargs):
        super(ApiError, self).__init__(**kwargs)

        self.code = code
        self.data = data
        self.msg = msg

        self.headers = kwargs.get("headers", {})

    def __str__(self):
        return str(self.data)


class AuthFailed(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Authorization failed"
        super(AuthFailed, self).__init__(401, msg=msg, data=data, **kwargs)
        self.headers["Authorization"] = "Basic"


class AccessForbidden(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Access forbidden"
        super(AccessForbidden, self).__init__(403, msg=msg, data=data, **kwargs)


class ObjectNotFoundError(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Requested object wasn't found"
        super(ObjectNotFoundError, self).__init__(404, msg=msg, data=data, **kwargs)


class ObjectAlreadyExists(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Operational error, trying to create existing object"

        super(ObjectAlreadyExists, self).__init__(409, msg=msg, data=data, **kwargs)


class MalformedRequest(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Given request contains errors or couldn't be executed in the current context"

        super(MalformedRequest, self).__init__(400, msg=msg, data=data, **kwargs)


class CannotProcessRequest(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Cannot process given request"

        super(CannotProcessRequest, self).__init__(400, msg=msg, data=data, **kwargs)


class ServerError(ApiError):
    def __init__(self, msg=None, data=None, **kwargs):
        if msg is None:
            msg = "Unhandled server error, please contact site administrator"
        super(ServerError, self).__init__(500, msg=msg, data=data, **kwargs)
