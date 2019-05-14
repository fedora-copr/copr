#!/usr/bin/python3

import os
import sys
import pwd
import time
from copr.v3 import Client
from copr.v3.exceptions import CoprNoResultException

sys.path.append("/usr/share/copr/")
from backend.helpers import BackendConfigReader


def main():
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    config = BackendConfigReader(config_file).read()
    client = Client({"copr_url": config.frontend_base_url})

    for ownername in os.listdir(config.destdir):
        ownerpath = os.path.join(config.destdir, ownername)

        for projectname in os.listdir(ownerpath):
            projectpath = os.path.join(ownerpath, projectname)

            # It may be a good idea, to not DoS attack the frontend
            # Set whatever number of seconds is necessary
            time.sleep(0)

            # If a project doesn't exist in frontend, it should be removed
            try:
                project = client.project_proxy.get(ownername=ownername, projectname=projectname)
            except CoprNoResultException:
                print(projectpath)
                continue

            # If a chroot is not enabled in the project, it should be removed
            for chroot in os.listdir(projectpath):
                if chroot in ["srpm-builds", "modules"]:
                    continue
                if chroot in project.chroot_repos:
                    continue
                print(os.path.join(projectpath, chroot))


if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        main()