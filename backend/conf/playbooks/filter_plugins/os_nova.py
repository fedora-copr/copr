from novaclient.client import Client

def nova_result_to_builder_ip(nova_result, network_name):
    return nova_result["addresses"][network_name][0]["addr"]


def network_name_to_id(network_name, username, password, tenant_name, auth_url):
    nt = Client('2', username, password, tenant_name, auth_url)
    return nt.networks.find(label=network_name).id


def image_name_to_id(image_name, username, password, tenant_name, auth_url):
    nt = Client('2', username, password, tenant_name, auth_url)
    return nt.images.find(name=image_name).id


def flavor_name_to_id(flavor_name, username, password, tenant_name, auth_url):
    nt = Client('2', username, password, tenant_name, auth_url)
    return nt.flavors.find(name=flavor_name).id


class FilterModule(object):
    def filters(self):
        return {
            "nova_result_to_builder_ip": nova_result_to_builder_ip,
            # "flavor_id_to_name": flavor_id_to_name,
            "flavor_name_to_id": flavor_name_to_id,
            # "image_id_to_name": image_id_to_name,
            "image_name_to_id": image_name_to_id,
            "network_name_to_id": network_name_to_id,
            # "network_id_to_name": network_id_to_name,
        }

