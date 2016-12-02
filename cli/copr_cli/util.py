# coding: utf-8

try:
    from progress.bar import Bar
except ImportError:
    progress = False
else:
    progress = True


def format_size(bytes_in):
    if bytes_in > 1000 * 1000:
        return '%.1fMB' % (bytes_in / 1000.0 / 1000)
    elif bytes_in > 10 * 1000:
        return '%ikB' % (bytes_in / 1000)
    elif bytes_in > 1000:
        return '%.1fkB' % (bytes_in / 1000.0)
    else:
        return '%ibytes' % bytes_in


class ProgressMixin(object):

    @property
    def download_speed(self):
        if self.avg == 0.0:
            return "..."
        return format_size(1 / self.avg) + "/s"

    @property
    def downloaded(self):
        return format_size(self.index)


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
