from .helpers import FailTypeEnum


class CoprDistGitException(Exception):
    strtype = 'unknown_error'


class PackageImportException(CoprDistGitException):
    strtype = 'srpm_import_failed'


class PackageDownloadException(CoprDistGitException):
    strtype = 'srpm_download_failed'


class SrpmBuilderException(CoprDistGitException):
    strtype = 'srpm_build_error'


class SrpmQueryException(CoprDistGitException):
    strtype = 'srpm_query_failed'


class GitCloneException(CoprDistGitException):
    strtype = 'git_clone_failed'


class GitWrongDirectoryException(CoprDistGitException):
    strtype = 'git_wrong_directory'


class GitCheckoutException(CoprDistGitException):
    strtype = 'git_checkout_error'


class TimeoutException(CoprDistGitException):
    strtype = 'timeout_exceeded'
