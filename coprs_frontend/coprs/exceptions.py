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

class ActionInProgressException(BaseException):
    def __init__(self, msg, action):
        self.msg = msg
        self.action = action
