from munch import Munch


class CoprException(Exception):
    """
    Base Copr exception
    """
    def __init__(self, msg=None, response=None):
        super(CoprException, self).__init__(msg)
        msg = msg or "Unspecified error"
        self.result = Munch(error=msg, __response__=response)


class CoprRequestException(CoprException):
    """
    Raised when the API request doesn't proceed successfully
    """
    def __str__(self):
        errors = self.result.error.split("\n")

        # A list of errors signalizes a form validation error
        # If there is only one error in the list, just return its value
        if len(errors) == 1:
            return str(errors[0])

        # Show one error per line
        result = ""
        for error in errors:
            result += "\n- {0}".format(error)
        return result


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
    We left this exception in our code because someone can still catch it
    """
    pass


class CoprConfigException(CoprException):
    """
    Exception thrown when the config file is incomplete or malformed.
    """
    pass


class CoprAuthException(CoprException):
    """
    Copr authentication failure
    """
