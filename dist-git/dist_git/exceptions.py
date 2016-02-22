from .helpers import FailTypeEnum

# coding: utf-8
class PackageImportException(Exception):
    pass


class PackageDownloadException(Exception):
    pass


class PackageQueryException(Exception):
    pass


class SrpmBuilderException(Exception):
    """
    error_code is defined in FailTypeEnum
    """
    def __init__(self, error_code=None):
        self.code = error_code

    def __str__(self):
        return FailTypeEnum(self.code)


class GitException(SrpmBuilderException):
    pass


class PyPIException(SrpmBuilderException):
    pass


class GitAndTitoException(GitException):
    def __init__(self, error_code=None):
        super(GitAndTitoException, self).__init__(error_code)
        if not error_code:
            self.code = FailTypeEnum("tito_general_error")
