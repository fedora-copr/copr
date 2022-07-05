# coding: utf-8

import humanize
import simplejson


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
    return simplejson.dumps(serializable(result), indent=4, sort_keys=True, for_json=True)
