#!/usr/bin/python

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import os
import sys
import logging
from subprocess import Popen, PIPE

from copr.client.exceptions import CoprException, CoprRequestException

sys.path.append("/usr/share/copr/")

from backend.helpers import BackendConfigReader, get_auto_createrepo_status
from backend.createrepo import createrepo_unsafe

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

DEF_DAYS = 14
DEF_PRUNE_SCRIPT = "/usr/bin/copr_prune_old_builds.sh"


def list_subdir(path):
    dir_names = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    return dir_names, map(lambda x: os.path.join(path, x), dir_names)


def prune_project(opts, path, username, projectname):
    log.debug("Going to prune {}/{}".format(username, projectname))
    # get ACR
    try:
        if not get_auto_createrepo_status(opts.frontend_base_url, username, projectname):
            log.debug("Skipped {}/{} since auto createrepo option is disabled"
                      .format(username, projectname))
            return
    except (CoprException, CoprRequestException) as exception:
        log.debug("Failed to get project details for {}/{} with error: {}".format(
            username, projectname, exception))
        return

    # run prune project sh
    days = getattr(opts, "prune_days", DEF_DAYS)

    cmd = map(str, [DEF_PRUNE_SCRIPT, path, days])

    handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = handle.communicate()

    if handle.returncode != 0:
        print("Failed to prune old builds for copr {}/{}".format(username, projectname))
        print("STDOUT: \n{}".format(stdout.decode()))
        print("STDERR: \n{}".format(stderr.decode()))
        return

    # run createrepo
    log.debug("Prune done for {}/{}".format(username, projectname))
    try:
        retcode, stdout, stderr = createrepo_unsafe(path)
        if retcode != 0:
            print("Createrepo for {}/{} failed".format(username, projectname))
            print("STDOUT: \n{}".format(stdout.decode()))
            print("STDERR: \n{}".format(stderr.decode()))
    except Exception as exception:
        print("Createrepo for {}/{} failed with error: {}"
              .format(username, projectname, exception))


def main():
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    opts = BackendConfigReader(config_file).read()

    results_dir = opts.destdir
    log.info("Pruning results dir: {} ".format(results_dir))
    user_dir_names, user_dirs = list_subdir(results_dir)

    print("Going to process total number: {} of user's directories".format(len(user_dir_names)))
    log.info("Going to process user's directories: {}".format(user_dir_names))

    counter = 0
    for username, subpath in zip(user_dir_names, user_dirs):
        log.debug("For user `{}` exploring path: {}".format(username, subpath))
        for projectname, project_path in zip(*list_subdir(subpath)):
            log.debug("Exploring project `{}` with path: {}".format(projectname, project_path))
            prune_project(opts, project_path, username, projectname)

            counter += 1
            print("Pruned {}. projects".format(counter))

    print("Pruning finished")


if __name__ == "__main__":
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    #     datefmt='%H:%M:%S'
    # )
    main()
