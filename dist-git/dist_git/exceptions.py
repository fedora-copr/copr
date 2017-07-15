class PackageImportException(Exception):
    strtype = 'unknown_error'


class RunCommandException(PackageImportException):
    strtype = 'shell_command_failed'


class FileDownloadException(PackageImportException):
    strtype = 'download_failed'


class SrpmQueryException(PackageImportException):
    strtype = 'srpm_query_failed'


class GitCloneException(PackageImportException):
    strtype = 'git_clone_failed'


class GitWrongDirectoryException(PackageImportException):
    strtype = 'git_wrong_directory'


class GitCheckoutException(PackageImportException):
    strtype = 'git_checkout_error'


class TimeoutException(PackageImportException):
    strtype = 'import_timeout_exceeded'


class RpmSpecParseException(PackageImportException):
    strtype = 'parse_spec_error'


class PackageNameCouldNotBeObtainedException(PackageImportException):
    strtype = 'obtain_package_name_error'
