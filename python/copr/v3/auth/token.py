"""
Authentication via (login, token)
"""

from copr.v3.auth.base import BaseAuth


class ApiToken(BaseAuth):
    """
    The standard authentication via `(login, token)` from `~/.config/copr`.
    """

    def __init__(self, *args, **kwargs):
        super(ApiToken, self).__init__(*args, **kwargs)
        # No need to lazy-login
        self.make()

    def make(self, reauth=False):
        """
        Override the higher abstraction method BaseAuth.make() because we don't
        need the complicated logic with API tokens at all (working with caches
        or sessions, etc.).  We also don't use make_expensive() at all.
        """
        self.auth = self.config["login"], self.config["token"]
        self.username = self.config.get("username")

    def make_expensive(self):
        """
        This is never called.  We have overridden the parent's make() method.
        """
        raise RuntimeError("ApiToken.make_expensive() should never be called")
