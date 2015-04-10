#!/usr/bin/python

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import os
import shutil
import sys
import logging
from subprocess import Popen, PIPE
import time
import pwd


log = logging.getLogger(__name__)


from copr.client.exceptions import CoprException, CoprRequestException

sys.path.append("/usr/share/copr/")

from backend.helpers import BackendConfigReader, get_auto_createrepo_status
from backend.createrepo import createrepo_unsafe


DEF_DAYS = 14
DEF_FIND_OBSOLETE_SCRIPT = "/usr/bin/copr_find_obsolete_builds.sh"


def list_subdir(path):
    dir_names = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    return dir_names, map(lambda x: os.path.join(path, x), dir_names)


class Pruner(object):
    def __init__(self, opts):
        self.opts = opts
        self.days = getattr(self.opts, "prune_days", DEF_DAYS)
        self.find_obsolete_script = getattr(self.opts, "find_obsolete_script", DEF_FIND_OBSOLETE_SCRIPT)

    def prune_failed_builds(self, chroot_path):
        """
        Deletes subdirs (project directories) which contains file `fail`
            with mtime older then self.days

        :param chroot_path: path to the chroot directory
        """
        for sub_dir_name in os.listdir(chroot_path):
            build_path = os.path.join(chroot_path, sub_dir_name)
            if not os.path.isdir(build_path):
                # log.debug("Not a project directory, skipping: {}".format(build_path))
                continue

            fail_file_path = os.path.join(build_path, "fail")
            if os.path.exists(fail_file_path) and not os.path.exists(os.path.join(build_path, "success")):
                if time.time() - os.path.getmtime(fail_file_path) > self.days:
                    log.info("Removing failed build: {}".format(build_path))
                    shutil.rmtree(build_path)

    def prune_obsolete_success_builds(self, chroot_path):
        """
        Uses bash script which invokes repoquery to find obsolete build_dirs

        :param chroot_path: path to the chroot directory
        """
        # import ipdb; ipdb.set_trace()
        cmd = map(str, [self.find_obsolete_script, chroot_path, self.days])
        handle = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = handle.communicate()
        if handle.returncode != 0:
            log.error("Failed to prune old builds at: {} \n STDOUT: \n{}\n STDERR: \n{}\n"
                      .format(chroot_path, stdout.decode(), stderr.decode()))
            return
        # log.debug("find obsolete returned:\n {}\n stderr: \n {}".format(stdout, stderr))
        for line in stdout.split("\n"):
            if not line.strip() or (len(line) > 0 and line[0] == "#"):
                continue
            to_delete = line.strip()
            log.debug("Obsolete path, check for remove: {}".format(to_delete))

            if to_delete in os.listdir(chroot_path):
                to_delete_path = os.path.join(chroot_path, to_delete)
                if os.path.isdir(to_delete_path):
                    log.info("Removing obsolete build: {}".format(to_delete_path))
                    shutil.rmtree(to_delete_path)

    def run(self):
        results_dir = self.opts.destdir
        log.info("Pruning results dir: {} ".format(results_dir))
        user_dir_names, user_dirs = list_subdir(results_dir)

        log.info("Going to process total number: {} of user's directories".format(len(user_dir_names)))
        log.info("Going to process user's directories: {}".format(user_dir_names))

        counter = 0
        for username, subpath in zip(user_dir_names, user_dirs):
            log.debug("For user `{}` exploring path: {}".format(username, subpath))
            for projectname, project_path in zip(*list_subdir(subpath)):
                log.debug("Exploring project `{}` with path: {}".format(projectname, project_path))
                self.prune_project(project_path, username, projectname)

                counter += 1
                log.info("Pruned {}. projects".format(counter))

        log.info("Pruning finished")

    def prune_project(self, project_path, username, projectname):
        log.info("Going to prune {}/{}".format(username, projectname))
        # get ACR
        try:
            if not get_auto_createrepo_status(self.opts.frontend_base_url, username, projectname):
                log.debug("Skipped {}/{} since auto createrepo option is disabled"
                          .format(username, projectname))
                return
        except (CoprException, CoprRequestException) as exception:
            log.debug("Failed to get project details for {}/{} with error: {}".format(
                username, projectname, exception))
            return

        # run prune project sh
        for sub_dir_name in os.listdir(project_path):
            chroot_path = os.path.join(project_path, sub_dir_name)
            if not os.path.isdir(chroot_path):
                continue

            try:
                self.prune_failed_builds(chroot_path)
                self.prune_obsolete_success_builds(chroot_path)
            except Exception as err:
                log.exception(err)
                log.error("Error during prune copr {}/{}:{}".format(username, projectname, sub_dir_name))

            log.debug("Prune done for {}/{}:{}".format(username, projectname, sub_dir_name))
            # run createrepo

            try:
                retcode, stdout, stderr = createrepo_unsafe(chroot_path)
                if retcode != 0:
                    log.error(
                        "Failed to createrepo for copr {}/{}:{}\n STDOUT: \n{}\n STDERR: \n{}\n"
                        .format(username, projectname, sub_dir_name, stdout.decode(), stderr.decode()))
                else:
                    log.info("Createrepo done for copr {}/{}:{}"
                             .format(username, projectname, sub_dir_name))
            except Exception as exception:
                log.exception("Createrepo for copr {}/{}:{} failed with error: {}"
                              .format(username, projectname, sub_dir_name, exception))

        log.info("Prune finished for copr {}/{}".format(username, projectname))


def main():
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    pruner = Pruner(BackendConfigReader(config_file).read())
    pruner.run()

if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        logging.basicConfig(
            filename="/var/log/copr/prune_old.log",
            format='[%(asctime)s][%(levelname)6s]: %(message)s',
            level=logging.INFO)
        main()
