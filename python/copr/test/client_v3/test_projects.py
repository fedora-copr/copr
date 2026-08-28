from copr.test import config_location, mock
from copr.v3 import Client
from copr.v3.proxies.project import UserPermissions


class TestProjectProxy(object):
    @mock.patch("copr.v3.proxies.Request.send")
    def test_add(self, send):
        client = Client.create_from_config_file(config_location)
        client.project_proxy.add("user1", "foo", ["fedora-rawhide-x86_64"])
        assert len(send.call_args_list) == 1
        call = send.call_args_list[0]
        args = call[1]
        assert args["method"] == "POST"
        assert args["params"]["ownername"] == "user1"
        assert args["data"]["name"] == "foo"

    @mock.patch("copr.v3.proxies.Request.send")
    def test_set_permissions(self, send):
        client = Client.create_from_config_file(config_location)
        permissions: UserPermissions = {
            "user1": {
                "builder": "approved",
                "admin": "nothing",
            }
        }
        client.project_proxy.set_permissions("user1", "foo", permissions)
        assert len(send.call_args_list) == 1
        call = send.call_args_list[0]
        args = call[1]
        assert args["method"] == "PUT"
        assert args["data"]["user1"] == {
            "admin": "nothing",
            "builder": "approved",
        }
