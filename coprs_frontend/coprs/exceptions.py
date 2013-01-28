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
