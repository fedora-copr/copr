class PackageImportException(Exception):
    strtype = 'unknown_error'


class RunCommandException(PackageImportException):
    strtype = 'shell_command_failed'


class FileDownloadException(PackageImportException):
    strtype = 'download_failed'


class TimeoutException(PackageImportException):
    strtype = 'import_timeout_exceeded'


class SrpmQueryException(PackageImportException):
    strtype = 'srpm_query_exception'
