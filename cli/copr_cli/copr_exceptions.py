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
