from copr.v3.proxies import BaseProxy


class TestBaseProxy(object):
    def test_api_base_url(self):
        proxy = BaseProxy({"copr_url": "http://copr"})
        assert proxy.api_base_url == "http://copr/api_3/"

        # Slashes or port number should not be a problem
        proxy = BaseProxy({"copr_url": "http://copr:5000/"})
        assert proxy.api_base_url == "http://copr:5000/api_3/"
