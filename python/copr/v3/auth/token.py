"""
Authentication via (login, token)
"""

from copr.v3.auth.base import BaseAuth


class ApiToken(BaseAuth):
    """
    The standard authentication via `(login, token)` from `~/.config/copr`
    """
    def make_expensive(self):
        self.auth = self.config["login"], self.config["token"]
        self.username = self.config.get("username")
