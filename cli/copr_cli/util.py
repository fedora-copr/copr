# coding: utf-8

import socket
from datetime import timedelta

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


def listen_for_token():
    """
    Function taken from https://pagure.io/fm-orchestrator/blob/master/f/contrib/submit_build.py
    We should avoid code duplicity by including it into _some_ python module

    Listens on port 13747 on localhost for a redirect request by OIDC
    server, parses the response and returns the "access_token" value.
    """
    TCP_IP = '0.0.0.0'
    TCP_PORT = 13747
    BUFFER_SIZE = 1024

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((TCP_IP, TCP_PORT))
    s.listen(1)

    conn, addr = s.accept()
    data = ""
    sent_resp = False
    while 1:
        try:
            r = conn.recv(BUFFER_SIZE)
        except:
            conn.close()
            break
        if not r: break
        data += r.decode("utf-8")

        if not sent_resp:
            response = "Token has been handled."
            conn.send("""HTTP/1.1 200 OK
Content-Length: {}
Content-Type: text/plain
Connection: Closed

{}""".format(len(response), response).encode("utf-8"))
            conn.close()
            sent_resp = True

    s.close()

    data = data.split("\n")
    for line in data:
        variables = line.split("&")
        for var in variables:
            kv = var.split("=")
            if not len(kv) == 2:
                continue
            if kv[0] == "access_token":
                return kv[1]
    return None
