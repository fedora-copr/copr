# coding: utf-8


class Config(object):
    OS_AUTH_URL = "https://fed-cloud09.cloud.fedoraproject.org:5000/v2.0"

    # With the addition of Keystone we have standardized on the term **tenant**
    # as the entity that owns the resources.
    # OS_TENANT_ID = "a3fa9697346046ef9e691a21527923a5"
    # OS_TENANT_NAME = "copr"
    OS_TENANT_ID = "566a072fb1694950998ad191fee3833b"
    OS_TENANT_NAME = "coprdev"

    # In addition to the owning entity (tenant), openstack stores the entity
    # performing the action as the **user**.
    OS_USERNAME = "username"
    OS_PASSWORD = "password"

    # If your configuration has multiple regions, we set that information here.
    # OS_REGION_NAME is optional and only valid in certain environments.
    OS_REGION_NAME = "RegionOne"

    flavor_name = "m1.small"

    vm_name = "builder_base_image"
    image_name = "Fedora-Cloud-Base-20141203-21"
    key_name = "fas"

    net_name_list = ["coprdev-net", "copr-net", "external"]
    security_groups = ["default", "ssh-anywhere-coprdev"]

    provision_pb_path = ""

    floating_ips_pool = "external"
