#!/usr/bin/python2

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import os
import shutil
import sys
import logging
import subprocess
import pwd

log = logging.getLogger(__name__)

from copr.exceptions import CoprException
from copr.exceptions import CoprRequestException

sys.path.append("/usr/share/copr/")

from backend.helpers import BackendConfigReader
from backend.helpers import get_auto_createrepo_status

DEF_DAYS = 14

def list_subdir(path):
    dir_names = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    return dir_names, map(lambda x: os.path.join(path, x), dir_names)

def logdebug(msg):
    print(msg)
    log.debug(msg)

def loginfo(msg):
    print(msg)
    log.info(msg)

def logerror(msg):
    print(msg, file=sys.stderr)
    log.error(msg)

def logexception(msg):
    print(msg, file=sys.stderr)
    log.exception(msg)

def runcmd(cmd):
    """
    Run given command in a subprocess
    """
    loginfo('Executing: '+' '.join(cmd))
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = process.communicate()
    if process.returncode != 0:
        logerror(stderr)
        raise Exception("Got non-zero return code ({0}) from prunerepo with stderr: {1}".format(process.returncode, stderr))
    return stdout


class Pruner(object):
    def __init__(self, opts):
        self.opts = opts
        self.prune_days = getattr(self.opts, "prune_days", DEF_DAYS)

    def run(self):
        results_dir = self.opts.destdir
        loginfo("Pruning results dir: {} ".format(results_dir))
        user_dir_names, user_dirs = list_subdir(results_dir)

        loginfo("Going to process total number: {} of user's directories".format(len(user_dir_names)))
        loginfo("Going to process user's directories: {}".format(user_dir_names))

        loginfo("--------------------------------------------")
        for username, subpath in zip(user_dir_names, user_dirs):
            loginfo("For user `{}` exploring path: {}".format(username, subpath))
            for projectname, project_path in zip(*list_subdir(subpath)):
                loginfo("Exploring project `{}` with path: {}".format(projectname, project_path))
                self.prune_project(project_path, username, projectname)
                loginfo("--------------------------------------------")

        loginfo("Pruning finished")

    def prune_project(self, project_path, username, projectname):
        loginfo("Going to prune {}/{}".format(username, projectname))

        try:
            if not get_auto_createrepo_status(self.opts.frontend_base_url, username, projectname):
                loginfo("Skipped {}/{} since auto createrepo option is disabled"
                          .format(username, projectname))
                return
        except (CoprException, CoprRequestException) as exception:
            logerror("Failed to get project details for {}/{} with error: {}".format(
                username, projectname, exception))
            return

        for sub_dir_name in os.listdir(project_path):
            chroot_path = os.path.join(project_path, sub_dir_name)
            if not os.path.isdir(chroot_path):
                continue

            try:
                cmd = ['prunerepo', '--verbose', '--days={0}'.format(self.prune_days), '--cleancopr', chroot_path]
                stdout = runcmd(cmd)
                loginfo(stdout)
            except Exception as err:
                logexception(err)
                logerror("Error pruning chroot {}/{}:{}".format(username, projectname, sub_dir_name))

            loginfo("Pruning done for chroot {}/{}:{}".format(username, projectname, sub_dir_name))

        loginfo("Pruning finished for project {}/{}".format(username, projectname))


def main():
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    pruner = Pruner(BackendConfigReader(config_file).read())
    try:
        pruner.run()
    except Exception as e:
        logexception(e)

if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        logging.basicConfig(
            filename="/var/log/copr-backend/copr_prune_results.log",
            format='[%(asctime)s][%(levelname)6s]: %(message)s',
            level=logging.INFO)
        main()
