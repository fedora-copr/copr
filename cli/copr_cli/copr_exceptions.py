#-*- coding: UTF-8 -*-

"""
Exceptions for copr-cli
"""


class CoprCliException(Exception):

    """ Basic exception class for copr-cli. """
    pass


class CoprCliNoConfException(CoprCliException):

    """ Exception thrown when no config file is found. """
    pass


class CoprCliConfigException(CoprCliException):

    """ Exception thrown when the config file is incomplete or
    malformated.
    """
    pass


class CoprCliRequestException(Exception):
    """ Exception thrown when the request is bad. For example,
    the user provided wrong project name or build ID. 
    """
    pass


class CoprCliBuildException(Exception):
    """ Exception thrown when one or more builds fail and Cli is waiting
    for the result.
    """
    pass


class CoprCliUnknownResponseException(Exception):
    """ Exception thrown when the response is unknown to cli.
    It usualy means that something is broken.
    """
    pass
