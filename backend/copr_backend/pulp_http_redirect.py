"""
Maintain a list of HTTP redirects to Pulp
"""

from copr_common.lock import lock
from .constants import PULP_REDIRECT_FILE


class PulpHTTPRedirect:
    """
    Maintain a list of Copr projects that have data in Pulp and therefore need
    HTTP redirects there. See the redirect script here:
    https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/backend/templates/lighttpd/pulp-redirect.lua.j2
    """

    def __init__(self, path=None, lockdir=None, log=None):
        self.path = path or PULP_REDIRECT_FILE
        self.lockdir = lockdir or "/var/lock/copr-backend"
        self.log = log
        if not self.log:
            raise NotImplementedError("Default logger not implemented yet")

    def add(self, owner, project):
        """
        Create a HTTP redirect for this project.
        """
        fullname = "{0}/{1}".format(owner, project)
        try:
            with open(self.path, "r", encoding="utf-8") as fp:
                projects = fp.read().splitlines()

            if fullname in projects:
                return

            with lock(self.path, lockdir=self.lockdir, log=self.log):
                with open(self.path, "r", encoding="utf-8") as fp:
                    projects = fp.read().splitlines()

                with open(self.path, "a", encoding="utf-8") as fp:
                    print(fullname, file=fp)

        except FileNotFoundError:
            # Ignoring because this Copr instance doesn't need redirects
            pass

    def remove(self, owner, dirname):
        """
        Remove a HTTP redirect for this project.
        """
        fullname = "{0}/{1}".format(owner, dirname)
        try:
            with open(self.path, "r", encoding="utf-8") as fp:
                projects = fp.read().splitlines()

            if fullname not in projects:
                return

            with lock(self.path, lockdir=self.lockdir, log=self.log):
                with open(self.path, "r", encoding="utf-8") as fp:
                    projects = fp.read().splitlines()

                filtered_projects = [p for p in projects if p != fullname]
                with open(self.path, "w", encoding="utf-8") as fp:
                    for project in filtered_projects:
                        print(project, file=fp)

        except FileNotFoundError:
            # Ignoring because this Copr instance doesn't need redirects
            pass
