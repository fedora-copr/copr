from .helpers import FailTypeEnum

# coding: utf-8
class PackageImportException(Exception):
    pass


class PackageDownloadException(Exception):
    pass


class PackageQueryException(Exception):
    pass


class GitAndTitoException(Exception):
    """
    error_code is defined in FailTypeEnum
    """
    def __init__(self, error_code=None):
        self.code = FailTypeEnum("tito_general_error")

        if error_code:
            self.code = error_code

    def __str__(self):
        return FailTypeEnum(self.code)
