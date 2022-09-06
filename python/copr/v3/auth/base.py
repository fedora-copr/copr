"""
Base authentication interface
"""

import os
import json
import time
import errno
from filelock import FileLock

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class BaseAuth(object):
    """
    Base authentication class
    There is a more standard way of implementing custom authentication classes,
    please see https://docs.python-requests.org/en/latest/user/authentication/
    We can eventually implement it using `requests.auth`.
    """

    def __init__(self, config):
        self.config = config
        self.cache = AuthCache(config)
        self.username = None
        self.expiration = None

        # These attributes will be directly passed to the requests.request(...)
        # calls. Various authentication mechanisms should set them accordingly.
        self.auth = None
        self.cookies = None

    @property
    def expired(self):
        """
        Are the authentication tokens, cookies, etc, expired?

        We know this for example for cached cookies. It can be tricky because
        it can be expired regardless of the expiration time when frontend
        decides to e.g. revoke all tokens, but we get to know only when sending
        a request.

        But when expiration time is gone, we for sure know the cookie is
        expired. That will help us avoid sending requests that we know will be
        unsuccessful.
        """
        if not self.expiration:
            return False
        return self.expiration < time.time()

    def make_expensive(self):
        """
        Perform the authentication process. This is the most expensive part.
        The point is to set `self.username`, and some combination of
        `self.auth` and `self.cookies`.
        """
        raise NotImplementedError

    def make(self, reauth=False):
        """
        Perform the authentication process. It can be expensive, so we ensure
        caching with locks, expiration checks, etc.
        If `reauth=True` is set, then any cached cookies are ignored and the
        authentication is done from scratch
        """
        # If we know an username, the authentication must have been done
        # previously and there is no need to do it again.
        # Unless we specifically request an re-auth
        auth_done = bool(self.username) and not reauth
        if auth_done:
            return

        with self.cache.lock:
            # Try to load session data from cache
            if not reauth and self._load_cache():
                auth_done = True

            # If we don't have any cached cookies or they are expired
            if not auth_done or self.expired:
                self.make_expensive()
                self._save_cache()

    def _load_cache(self):
        session_data = self.cache.load_session()
        if session_data:
            token = session_data["session"]
            self.username = session_data["name"]
            self.cookies = {"session": token}
            self.expiration = session_data["expiration"]
        return bool(session_data)

    def _save_cache(self):
        # For now, we don't want to cache (login, token) information, only
        # session cookies (for e.g. GSSAPI)
        if not self.cookies:
            return

        data = {
            "name": self.username,
            "session": self.cookies["session"],
            "expiration": self.expiration,
        }
        self.cache.save_session(data)


class AuthCache:
    """
    Some authentication methods are expensive and we want to use them only
    for an initial authentication, chache their value, and use until expiration.
    """

    def __init__(self, config):
        self.config = config

    @property
    def session_file(self):
        """
        Path to the cached file for a given Copr instance
        """
        url = urlparse(self.config["copr_url"]).netloc
        cachedir = os.path.join(os.path.expanduser("~"), ".cache", "copr")
        try:
            os.makedirs(cachedir)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        return os.path.join(cachedir, url + "-session")

    @property
    def lock_file(self):
        """
        Path to the lock file for a given Copr instance
        """
        return self.session_file + ".lock"

    @property
    def lock(self):
        """
        Allow the user to do `with cache.lock:`
        """
        return FileLock(self.lock_file)

    def load_session(self):
        """
        Load the session data from a cache file
        """
        if not os.path.exists(self.session_file):
            return None
        with open(self.session_file, "r") as fp:
            return json.load(fp)

    def save_session(self, session_data):
        """
        Save the session data to a cache file
        """
        with open(self.session_file, "w") as file:
            session_data["expiration"] = time.time() + 10 * 3600  # +10 hours
            file.write(json.dumps(session_data, indent=4) + "\n")
