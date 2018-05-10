class CoprException(Exception):
    """
    Base Copr exception
    """
    pass


class CoprRequestException(CoprException):
    """
    Raised when the API request doesn't proceed successfully
    """
    pass


class CoprValidationException(CoprException):
    """
    Raised when the data sent from client to API are not valid
    """
    pass
