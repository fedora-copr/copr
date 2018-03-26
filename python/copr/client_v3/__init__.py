from __future__ import absolute_import

from .requests import Request, Response, GET, POST, CoprRequestException
from .proxies.build import BuildProxy
from .proxies.package import PackageProxy


# @TODO give some love to the Client class
class Client(object):
    def __init__(self):
        self.builds = BuildProxy(None)


__all__ = [
    GET,
    POST,
    Client,
    BuildProxy,
    PackageProxy,
    CoprRequestException,
]
