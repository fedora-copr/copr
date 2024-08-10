# coding: utf-8

import json
import humanize


try:
    from progress.bar import Bar

    class SpeedProgressBar(Bar):
        """
        Modified progress.bar.Bar with additional formatters %(download_speed)
        and %(downloaded), with additional interface supported by
        MultipartEncoderMonitor API.
        Bar accepts the last N downloaded bytes, while MultipartEncoderMonitor
        callback provides the total number of downloaded bytes.  N needs to be
        calculated.
        """

        message = "%(percent)d%%"
        suffix = "%(downloaded)s %(download_speed)s eta %(eta_td)s"
        read_last = 0

        @property
        def download_speed(self):
            """ Inverted value of Bar.avg """
            if self.avg == 0.0:
                return "..."
            return "{0}/s".format(humanize.naturalsize(1 / self.avg))

        @property
        def downloaded(self):
            """ How many bytes are already downloaded """
            return humanize.naturalsize(self.index)

        def __call__(self, monitor):
            """ MultipartEncoderMonitor expects callable """
            read = monitor.bytes_read - self.read_last
            self.read_last = monitor.bytes_read
            self.next(read)


except ImportError:
    progress = False
else:
    progress = True


def get_progress_callback(length):
    """
    If python-progress is installed, instantiate progress bar object.  Otherwise
    just return None.
    """
    if not progress:
        return None
    return SpeedProgressBar(max=length)


def serializable(result):
    if isinstance(result, dict):
        new_result = dict(result)
        new_result.pop("__response__", None)
        new_result.pop("__proxy__", None)
        return new_result
    return result


def json_dumps(result):
    return json.dumps(serializable(result), indent=4, sort_keys=True)


def package_version(name):
    """
    Return version of a given Python package

    The `importlib.metadata` module was introduced in Python 3.8 while
    EPEL 8 has Python 3.6. At the same time, `pkg_resources` is deprecated
    since Python 3.12 (Fedora 40):
    """
    # pylint: disable=import-outside-toplevel
    try:
        from importlib.metadata import distribution, PackageNotFoundError
        try:
            return distribution(name).version
        except PackageNotFoundError:
            return "git"
    except ImportError:
        import pkg_resources
        try:
            return pkg_resources.require(name)[0].version
        except pkg_resources.DistributionNotFound:
            return "git"
