# coding: utf-8

import humanize
import simplejson


try:
    from progress.bar import Bar
except ImportError:
    progress = False
else:
    progress = True


class ProgressMixin(object):

    @property
    def download_speed(self):
        if self.avg == 0.0:
            return "..."
        return "{0}/s".format(humanize.naturalsize(1 / self.avg))

    @property
    def downloaded(self):
        return humanize.naturalsize(self.index)


class DummyBar(object):
    # pylint: disable=redefined-builtin
    def __init__(self, max=None):
        pass

    def next(self, n=None):
        pass

    def finish(self):
        pass


if progress:
    class ProgressBar(Bar, ProgressMixin):
        message = "%(percent)d%%"
        suffix = "%(downloaded)s %(download_speed)s eta %(eta_td)s"
else:
    ProgressBar = DummyBar


def serializable(result):
    if isinstance(result, dict):
        new_result = result.copy()
        new_result.pop("__response__", None)
        new_result.pop("__proxy__", None)
        return new_result
    return result


def json_dumps(result):
    return simplejson.dumps(serializable(result), indent=4, sort_keys=True, for_json=True)
