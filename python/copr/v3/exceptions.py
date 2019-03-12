from munch import Munch


class CoprException(Exception):
    """
    Base Copr exception
    """
    def __init__(self, msg=None, response=None):
        super(CoprException, self).__init__(msg)
        self.result = Munch(error=msg, __response__=response)


class CoprRequestException(CoprException):
    """
    Raised when the API request doesn't proceed successfully
    """
    pass


class CoprNoResultException(CoprException):
    """
    Raised when no result data is returned
    """
    pass


class CoprTimeoutException(CoprException):
    """
    Raised when the API request timeouted
    """
    pass


class CoprValidationException(CoprException):
    """
    Raised when the data sent from client to API are not valid
    """
    pass


class CoprNoConfigException(CoprException):
    """
    Exception thrown when no config file is found
    """
    pass


class CoprConfigException(CoprException):
    """
    Exception thrown when the config file is incomplete or malformed.
    """
    pass
