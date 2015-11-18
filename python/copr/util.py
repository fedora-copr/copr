# coding: utf-8
import sys


# pylint: disable=R0903
class UnicodeMixin(object):
    # http://lucumr.pocoo.org/2011/1/22/forwards-compatible-python/
    """Mixin class to handle defining the proper __str__/__unicode__
    methods in Python 2 or 3."""

    if sys.version_info[0] >= 3:  # Python 3
        def __str__(self):
            return self.__unicode__()
    else:  # Python 2
        def __str__(self):
            return self.__unicode__().encode('utf8')
