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
