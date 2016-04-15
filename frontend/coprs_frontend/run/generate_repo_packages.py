#!/usr/bin/python
# -*- coding: utf-8 -*-

# RUN
#     cd frontend/coprs_frontend
#     COPR_CONFIG=../config/copr_devel.conf python run/generate_repo_packages.py


from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import requests
import os
import shutil
import subprocess
import logging
from six.moves.urllib.parse import urljoin

here = os.path.dirname(os.path.realpath(__file__))
import sys
sys.path.append(os.path.dirname(here))

from coprs import app
from coprs.logic.coprs_logic import CoprsLogic


# ----------------------------------------------------------------------------------------------------------------------

hostname = app.config["PUBLIC_COPR_HOSTNAME"]
scheme = app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] if "ENFORCE_PROTOCOL_FOR_FRONTEND_URL" in app.config else "http"

FRONTEND_URL = "{}://{}".format(scheme, hostname)
FRONTEND_DIR = os.path.dirname(here)
PACKAGES_DIR = os.path.join(app.config["DATA_DIR"], "repo-rpm-packages")
RPMBUILD = os.path.join(os.path.expanduser("~"), "rpmbuild")
LOG_FILE = "/var/log/copr/repo-packages.log"

VERSION = 1
RELEASE = 1


# ----------------------------------------------------------------------------------------------------------------------

log = logging.getLogger(__name__)


class RepoRpmBuilder(object):

    RPM_NAME_FORMAT = "copr-repo-{}-{}-{}-{}-1-1.noarch.rpm"
    SPEC_NAME = "copr-repo-package.spec"

    def __init__(self, user, copr, chroot, topdir=RPMBUILD, packagesdir=PACKAGES_DIR):
        self.user = user                # Name of the user
        self.copr = copr                # Name of the copr
        self.chroot = chroot            # MockChroot object
        self.topdir = topdir            # rpmbuild directory (default $HOME/rpmbuild)
        self.packagesdir = packagesdir  # Directory where to store the rpm packages

    @property
    def rpm_name(self):
        version = self.chroot.os_version
        # All Fedora releases except for rawhide has same .repo file
        if self.chroot.os_release == "fedora" and self.chroot.os_version.isdigit():
            version = "all"
        return self.RPM_NAME_FORMAT.format(self.user, self.copr, self.chroot.os_release, version)

    @property
    def repo_name(self):
        return "{}-{}-{}-{}.repo"\
            .format(self.user, self.copr, self.chroot.os_release, self.chroot.os_version)

    def has_repo_package(self):
        return os.path.isfile(os.path.join(self.packagesdir, self.rpm_name))

    def get_repofile(self):
        api = "coprs/{}/{}/repo/{}/{}".format(self.user, self.copr, self.chroot.name_release, self.repo_name)
        url = urljoin(FRONTEND_URL, api)
        r = requests.get(url)
        if r.status_code != 200:
            raise RuntimeError("Can't get {}".format(url))
        return r.content

    def generate_repo_package(self):

        shutil.copyfile(os.path.join(FRONTEND_DIR, "coprs/templates/coprs/", self.SPEC_NAME),
                        os.path.join(self.topdir, "SPECS", self.SPEC_NAME))

        with open(os.path.join(self.topdir, "SOURCES", self.repo_name), "w") as f:
            f.writelines(self.get_repofile())

        defines = [
            "-D",       "_topdir {}".format(self.topdir),
            "-D",       "_rpmdir {}".format(self.packagesdir),
            "-D",  "_rpmfilename {}".format(self.rpm_name),
            "-D",      "pkg_name {}".format("copr-repo-{}-{}".format(self.user, self.copr)),
            "-D",   "pkg_version {}".format(VERSION),
            "-D",   "pkg_release {}".format(RELEASE),
            "-D",          "user {}".format(self.user),
            "-D",          "copr {}".format(self.copr),
            "-D",        "chroot {}".format("{}-{}".format(self.chroot.os_release, self.chroot.os_version)),
            "-D",      "repofile {}".format("_copr_{}-{}.repo".format(self.user, self.copr)),
        ]

        command = ["rpmbuild", "-ba"] + defines + [os.path.join(self.topdir, "SPECS", self.SPEC_NAME)]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()

        if process.returncode != 0:
            raise RuntimeError("Failed rpmbuild for: {}\n{}".format(self.repo_name, err))


# ----------------------------------------------------------------------------------------------------------------------


def all_coprs():
    return CoprsLogic.get_all()


# ----------------------------------------------------------------------------------------------------------------------

def prepare_rpmbuild_directory():
    dirs = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]
    for d in dirs:
        d = os.path.join(RPMBUILD, d)
        if not os.path.exists(d):
            os.makedirs(d)


def prepare_packages_directory():
    if not os.path.exists(PACKAGES_DIR):
        os.makedirs(PACKAGES_DIR)


def unique_chroots(copr):
    d = {}
    for chroot in copr.active_chroots:
        d[chroot.name_release] = chroot
    return d.values()


def main():
    prepare_rpmbuild_directory()
    prepare_packages_directory()

    for copr in all_coprs():
        for chroot in unique_chroots(copr):
            builder = RepoRpmBuilder(user=copr.user.name, copr=copr.name, chroot=chroot)

            if builder.has_repo_package():
                log.info("Skipping {}".format(builder.repo_name))
                continue

            try:
                builder.generate_repo_package()
                log.info("Created RPM package for: {}".format(builder.repo_name))

            except RuntimeError as e:
                log.error(e.message)


if __name__ == "__main__":
    try:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.basicConfig(
            filename=LOG_FILE,
            format='[%(asctime)s][%(levelname)6s]: %(message)s',
            level=logging.INFO)
        main()
    except KeyboardInterrupt:
        pass
