import os
import json
from datetime import datetime, timedelta

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
from ..helpers import config_from_file, get_session_cookie
from ..requests import Request, munchify
from ..helpers import for_all_methods, bind_proxy
from ..exceptions import CoprGssapiException


@for_all_methods(bind_proxy)
class BaseProxy(object):
    """
    Parent class for all other proxies
    """

    def __init__(self, config):
        self.config = config
        self._auth_token_cached = None

    @classmethod
    def create_from_config_file(cls, path=None):
        config = config_from_file(path)
        return cls(config)

    @property
    def api_base_url(self):
        return os.path.join(self.config["copr_url"], "api_3", "")

    @property
    def auth(self):
        if self._auth_token_cached:
            return self._auth_token_cached
        if self.config.get("token"):
            self._auth_token_cached = self.config["login"], self.config["token"]
        elif self.config.get("gssapi"):
            self._auth_token_cached = self._get_session_cookie_via_gssapi()
        return self._auth_token_cached

    def _get_session_cookie_via_gssapi(self):
        """Get session cookie using gssapi auth"""
        session_cookie = None
        url = urlparse(self.config["copr_url"]).netloc
        path_to_session_cookie = os.path.join(os.path.expanduser("~"), '.cache', 'copr', url + '-cookie')
        if os.path.exists(path_to_session_cookie):
            with open(path_to_session_cookie, 'r') as file:
                session_cookie = json.load(file)
        if not session_cookie or datetime.strptime(session_cookie["expiration"], '%Y-%m-%d %H:%M:%S') <= datetime.now():
            session_cookie = get_session_cookie(self.config)
            if session_cookie:
                cachedir = os.path.join(os.path.expanduser("~"), ".cache/copr")
                if not os.path.exists(cachedir):
                    os.makedirs(cachedir)
                with open(path_to_session_cookie, 'w') as file:
                    session_cookie_dict = {
                        "expiration": str(datetime.now() + timedelta(hours=10)).split('.', maxsplit=1)[0],
                        "value": session_cookie}
                    file.write(json.dumps(session_cookie_dict))
                return session_cookie
            raise CoprGssapiException("Operation requires api authentication")
        return session_cookie["value"]

    def home(self):
        """
        Call the Copr APIv3 base URL

        :return: Munch
        """
        endpoint = ""
        request = Request(endpoint, api_base_url=self.api_base_url)
        response = request.send()
        return munchify(response)

    def auth_check(self):
        """
        Call an endpoint protected by login to check whether the user auth key is valid

        :return: Munch
        """
        endpoint = "/auth-check"
        request = Request(endpoint, api_base_url=self.api_base_url, auth=self.auth)
        response = request.send()
        return munchify(response)
