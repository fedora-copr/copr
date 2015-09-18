# -*- coding: UTF-8 -*-

"""
Exceptions for Copr client.
"""


class CoprException(Exception):

    """ Basic exception class for Copr client. """
    pass


class CoprNoConfException(CoprException):

    """ Exception thrown when no config file is found. """
    pass


class CoprConfigException(CoprException):

    """ Exception thrown when the config file is incomplete or
    malformed.
    """
    pass


class CoprRequestException(CoprException):
    """ Exception thrown when the request is bad. For example,
    the user provided wrong project name or build ID.
    """
    pass


class CoprBuildException(CoprException):
    """ Exception thrown when one or more builds fail and client is waiting
    for the result.
    """
    pass


class CoprUnknownResponseException(CoprException):
    """ Exception thrown when the response is unknown to client.
    It usually means that something is broken.
    """
    pass
