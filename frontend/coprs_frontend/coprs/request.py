"""
Use NamedTemporaryFile for large file uploads, so we eventually don't have copy
the uploaded file to the final destination.
"""

import os
import tempfile
import typing as t

from werkzeug.formparser import default_stream_factory
import flask


NAMED_FILE_FROM_BYTES = 50*1024*1024


def get_request_class(app):
    """
    Return a Copr-specific Request class instantiated by Flask for every
    request.  We want to override the internal _get_file_stream() (HACK!) method
    to enforce using the NamedTemporaryFile class for the large uploaded files -
    instead of the werkzeug's default SpooledTemporaryFile.  While
    SpooledTemporaryFile() by default stores small files into memory and
    fallbacks to the /tmp directory, NamedTemporaryFile() data destination can
    be controlled by our Copr logic, so we can store the file into
    config[STORAGE_DIR] directly.  The slow uploads (typically network limits,
    from remote users' boxes) are thus directly stored to the target volume, and
    once uploaded we don't have to do the expensive cross-volume file copy
    (/tmp => STORAGE_DIR).  For very large source RPMs this could even mean
    several minutes.

    Be careful, we can't simply "move" the temporary file to the target
    destination because the upper level Flask/Werkzeug logic automatically
    unlinks the temporary file when the corresponding request is processed.
    We have to do os.link() instead.

    Reported to Flask upstream: https://github.com/pallets/flask/issues/4844
    """

    class _CoprRequestClass(flask.Request):
        # pylint: disable=no-self-use
        def _get_file_stream(
            self,
            total_content_length: t.Optional[int],
            content_type: t.Optional[str],
            filename: t.Optional[str] = None,
            content_length: t.Optional[int] = None,
        ) -> t.IO[bytes]:
            """Called to get a stream for the file upload."""

            # We do this hack only for reasonably large uploaded files,
            # elsewhere we use the default Flask upload mechanism.  This is to
            # stay as close to the upstream behavior as possible and stay
            # compatible in the future.
            if total_content_length and total_content_length >= NAMED_FILE_FROM_BYTES:
                # pylint: disable=consider-using-with
                tfile = tempfile.NamedTemporaryFile(
                    "rb+", dir=app.config["STORAGE_DIR"])
                setattr(tfile, "named_file", True)
                return t.cast(t.IO[bytes], tfile)

            # For the smaller RPMs, we keep using the default Temporary files
            # abstraction.
            return default_stream_factory(
                total_content_length,
                content_type,
                filename,
                content_length,
            )

    return _CoprRequestClass


def save_form_file_field_to(field, path: str):
    """
    Store the uploaded data on Werkzeug file field.  Use this if the hack
    with _CoprRequestClass above is in action, and when you are sure that the
    uploaded file is on the same partition with the target path (so we can
    hardlink).
    """
    stream = field.data.stream

    # Detect if SpooledTemporaryFile or NamedTemporaryFile is the storage
    if hasattr(stream, "named_file"):
        os.link(stream.name, path)
    else:
        field.data.save(path)
