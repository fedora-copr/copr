from .helpers import config_from_file
from .proxies import BaseProxy
from .proxies.project import ProjectProxy
from .proxies.build import BuildProxy
from .proxies.package import PackageProxy
from .proxies.module import ModuleProxy
from .proxies.mock_chroot import MockChrootProxy
from .proxies.project_chroot import ProjectChrootProxy
from .proxies.build_chroot import BuildChrootProxy
from .proxies.webhook import WebhookProxy


class Client(object):
    def __init__(self, config):
        self.config = config
        self.base_proxy = BaseProxy(config)
        self.project_proxy = ProjectProxy(config)
        self.build_proxy = BuildProxy(config)
        self.package_proxy = PackageProxy(config)
        self.module_proxy = ModuleProxy(config)
        self.mock_chroot_proxy = MockChrootProxy(config)
        self.project_chroot_proxy = ProjectChrootProxy(config)
        self.build_chroot_proxy = BuildChrootProxy(config)
        self.webhook_proxy = WebhookProxy(config)

    @classmethod
    def create_from_config_file(cls, path=None):
        config = config_from_file(path)
        return cls(config)
