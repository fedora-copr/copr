from .proxies.build import BuildProxy
from .proxies.package import PackageProxy


# @TODO give some love to the Client class
class Client(object):
    def __init__(self, config):
        self.config = config
        self.build_proxy = BuildProxy(config)
        self.package_proxy = PackageProxy(config)

    @classmethod
    def create_from_config_file(cls, path):
        pass
