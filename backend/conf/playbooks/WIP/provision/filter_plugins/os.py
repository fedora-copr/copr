from novaclient.v1_1.client import Client

def nova_result_to_builder_ip(nova_result, network_name):
    return nova_result["addresses"][network_name][0]["addr"]

def network_name_to_id(network_name, username, password, tenant_name, auth_url):
    nt = Client(username, password, tenant_name, auth_url, insecure=True)
    # import ipdb; ipdb.set_trace()
    return nt.networks.find(label=network_name).id
       


class FilterModule(object):
    def filters(self):
        return {
            "nova_result_to_builder_ip": nova_result_to_builder_ip,
            # "flavor_id_to_name": flavor_id_to_name,
            # "flavor_name_to_id": flavor_name_to_id,
            # "image_id_to_name": image_id_to_name,
            # "image_name_to_id": image_name_to_id,
            "network_name_to_id": network_name_to_id,
            # "network_id_to_name": network_id_to_name,
        }

