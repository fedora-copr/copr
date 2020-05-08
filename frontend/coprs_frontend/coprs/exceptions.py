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


class BadRequest(CoprHttpException):

    _default = "Bad request to the server"
    _code = 400


class ConflictingRequest(CoprHttpException):
    """ Generic DB conflict """
    _default = "Conflicting request"
    _code = 409


class ApiError(CoprHttpException):

    _default = "API error"
    _code = 500


class LegacyApiError(CoprHttpException):

    _default = "API error"
    _code = 500


class MalformedArgumentException(ValueError):
    pass


class NotFoundException(ObjectNotFound):
    pass


class DuplicateException(BadRequest):
    pass


class NonAdminCannotCreatePersistentProject(CoprHttpException):
    _default = "Non-admin cannot create persistent project."
    _code = 403


class NonAdminCannotDisableAutoPrunning(CoprHttpException):
    _default = "Non-admin cannot disable auto-prunning."
    _code = 403

InsufficientRightsException = AccessRestricted


class ActionInProgressException(CoprHttpException):

    def __init__(self, msg, action):
        super(ActionInProgressException, self).__init__(message=msg)
        self.msg = msg
        self.action = action

    def __unicode__(self):
        return self.formatted_msg()

    def __str__(self):
        return self.__unicode__()

    def formatted_msg(self):
        return self.msg.format(action=self.action)


class UnknownSourceTypeException(Exception):
    pass


class NoPackageSourceException(Exception):
    pass


class UnrepeatableBuildException(Exception):
    pass
