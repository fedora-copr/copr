#!/usr/bin/python
# coding: utf-8

"""
One-time run script to sign unsigned rpms and  place pubkey gpg to the all projects.
"""
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import shutil

import sys
import os
import logging
import pwd


logging.basicConfig(
    filename="/var/log/copr-backend/onetime_signer.log",
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)


sys.path.append("/usr/share/copr/")
from backend.helpers import BackendConfigReader, create_file_logger
from backend.sign import get_pubkey, sign_rpms_in_dir, create_user_keys
from backend.exceptions import CoprSignNoKeyError
from backend.createrepo import createrepo


def check_signed_rpms_in_pkg_dir(pkg_dir, user, project, chroot, chroot_dir, opts):
    success = True

    logger = create_file_logger("run.check_signed_rpms_in_pkg_dir",
                                "/tmp/copr_check_signed_rpms.log")
    try:
        sign_rpms_in_dir(user, project, pkg_dir, opts, log=logger)

        log.info("running createrepo for {}".format(pkg_dir))
        base_url = "/".join([opts.results_baseurl, user,
                             project, chroot])
        createrepo(
            path=chroot_dir,
            front_url=opts.frontend_base_url,
            base_url=base_url,
            username=user,
            projectname=project,
        )

    except Exception as err:
        success = False
        log.error(">>> Failed to check/sign rpm in dir pkg_dir")
        log.exception(err)

    return success


def check_signed_rpms(project_dir, user, project, opts):
    """
    Ensure that all rpm files are signed
    """
    success = True
    for chroot in os.listdir(project_dir):
        if not (chroot.startswith("fedora") or chroot.startswith("epel")):
            continue

        chroot_path = os.path.join(project_dir, chroot)
        if not os.path.isdir(chroot_path):
            continue

        log.debug("> Checking chroot `{}` in dir `{}`".format(chroot, project_dir))

        for mb_pkg in os.listdir(chroot_path):
            if mb_pkg in ["repodata", "devel"]:
                continue
            mb_pkg_path = os.path.join(chroot_path, mb_pkg)
            if not os.path.isdir(mb_pkg_path):
                continue

            log.debug(">> Stepping into package: {}".format(mb_pkg_path))

            if not check_signed_rpms_in_pkg_dir(mb_pkg_path, user, project, chroot, chroot_path, opts):
                success = False

    return success


def check_pubkey(pubkey_path, user, project, opts):
    """
    Ensure that pubkey.gpg presented in project/dir
    """
    if os.path.exists(pubkey_path):
        log.info("Pubkey for {}/{} exists: {}".format(user, project, pubkey_path))
        return True
    else:
        log.info("Missing pubkey for {}/{}".format(user, project))
        try:
            get_pubkey(user, project, pubkey_path)
            return True
        except Exception as err:
            log.exception(err)
            return False


def main():
    # shutil.rmtree("/tmp/users_failed.txt", ignore_errors=True)
    # shutil.rmtree("/tmp/users_done.txt", ignore_errors=True)
    users_done_old = set()
    try:
        with open("/tmp/users_done.txt") as handle:
            for line in handle:
                users_done_old.add(line.strip())
    except Exception as err:
        log.exception(err)
        log.debug("error during read old users done")

    opts = BackendConfigReader().read()
    log.info("Starting pubkey fill, destdir: {}".format(opts.destdir))

    log.debug("list dir: {}".format(os.listdir(opts.destdir)))
    for user_name in os.listdir(opts.destdir):
        if user_name in users_done_old:
            log.info("skipping user: {}".format(user_name))
            continue

        failed = False
        log.info("Started processing user dir: {}".format(user_name))
        user_dir = os.path.join(opts.destdir, user_name)

        for project_name in os.listdir(user_dir):
            log.info("Checking project dir: {}".format(project_name))

            try:
                get_pubkey(user_name, project_name)
                log.info("Key-pair exists for {}/{}".format(user_name, project_name))
            except CoprSignNoKeyError:
                create_user_keys(user_name, project_name, opts)
                log.info("Created new key-pair for {}/{}".format(user_name, project_name))
            except Exception as err:
                log.error("Failed to get pubkey for {}/{}, mark as failed, skipping")
                log.exception(err)
                failed = True
                continue

            project_dir = os.path.join(user_dir, project_name)
            pubkey_path = os.path.join(project_dir, "pubkey.gpg")
            if not check_signed_rpms(project_dir, user_name, project_name, opts):
                failed = False

            if not check_pubkey(pubkey_path, user_name, project_name, opts):
                failed = False

        if failed:
            with open("/tmp/users_failed.txt", "a") as handle:
                handle.write("{}\n".format(user_name))
        else:
            with open("/tmp/users_done.txt", "a") as handle:
                handle.write("{}\n".format(user_name))

if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        main()
