from .proxies.general import GeneralProxy
from .proxies.project import ProjectProxy
from .proxies.build import BuildProxy
from .proxies.package import PackageProxy
from .proxies.module import ModuleProxy
from .proxies.project_chroot import ProjectChrootProxy


class Client(object):
    def __init__(self, config):
        self.config = config
        self.general_proxy = GeneralProxy(config)
        self.project_proxy = ProjectProxy(config)
        self.build_proxy = BuildProxy(config)
        self.package_proxy = PackageProxy(config)
        self.module_proxy = ModuleProxy(config)
        self.project_chroot_proxy = ProjectChrootProxy(config)
