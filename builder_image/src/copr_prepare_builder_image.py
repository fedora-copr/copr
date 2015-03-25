# coding: utf-8


from ansible import errors, runner
from glanceclient  import Client as GlanceClient
from keystoneclient import session
from keystoneclient.auth.identity import v2 as identity
# from neutronclient.neutron.client import Client as NeutronClient
from novaclient.v2.client import Client
import glanceclient.exc
import json
import novaclient.exceptions

from config import Config


class ImageBuilder(object):

    """

    :type config: Config
    """
    def __init__(self, config):
        self.config = config
        self.vm_ip = None

        self.nova_result = None
        self.float_ip = None

    def post_init(self):
        self.nt = Client(
            self.config.OS_USERNAME,
            self.config.OS_PASSWORD,
            self.config.OS_TENANT_NAME,
            self.config.OS_AUTH_URL,
            insecure=True,
        )

    def spawn_vm(self):
        if len(self.nt.servers.findall(name=self.config.vm_name)) > 0:
            raise RuntimeError("Server already exists")

        nics = [
            {"net-id": net.id}
            for net in [
                self.nt.networks.find(human_id=net_name)
                for net_name in self.config.net_name_list
        ]]
        self.nova_result = self.nt.servers.create(
            name=self.config.vm_name,
            flavor=self.nt.flavors.find(name=self.config.flavor_name),
            image=self.nt.images.find(name=self.config.image_name),
            key_name=self.config.key_name,
            nics=nics,
            security_groups=self.config.security_groups,
        )

        if getattr(self.config, "floating_ips_pool"):
            self.float_ip = self.nt.floating_ips.create(pool=self.config.floating_ips_pool)
            self.nova_result.add_floating_ip(self.float_ip)

    def run_provision(self):
        pass

    def create_image_from_vm(self, image_name):
        pass


    def terminate_vm(self):
        if self.nova_result:
            self.nova_result.delete()
        if self.float_ip:
            self.float_ip.delete()


def main():
    ib = ImageBuilder(Config())
    try:
        ib.post_init()



    finally:
        ib.terminate_vm()


if __name__ == "__main__":
    main()
