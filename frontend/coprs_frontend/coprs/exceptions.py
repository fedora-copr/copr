class ArgumentMissingException(BaseException):
    pass


class MalformedArgumentException(ValueError):
    pass


class NotFoundException(BaseException):
    pass


class DuplicateException(BaseException):
    pass


class InsufficientRightsException(BaseException):
    pass


class RequestCannotBeExecuted(Exception):
    pass


class ActionInProgressException(BaseException):

    def __init__(self, msg, action):
        self.msg = msg
        self.action = action

    def __unicode__(self):
        return self.formatted_msg()

    def __str__(self):
        return self.__unicode__()

    def formatted_msg(self):
        return self.msg.format(action=self.action)


class CoprHttpException(Exception):

    _default = "Generic copr exception"
    _code = 500

    def __init__(self, message=None, code=None, **kwargs):
        self.message = message
        self.code = code or self._code
        self.kwargs = kwargs

    def __unicode__(self):
        return self.message or self._default

    def __str__(self):
        return self.__unicode__()


class ObjectNotFound(CoprHttpException):

    _default = "Requested object was not found"
    _code = 404


class AccessRestricted(CoprHttpException):

    _default = "You don't have required permission"
    _code = 403


class LegacyApiError(CoprHttpException):

    _default = "API error"
    _code = 500
