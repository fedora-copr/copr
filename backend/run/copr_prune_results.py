#!/usr/bin/python3

import logging
import os
import shutil
import sys
import subprocess
import pwd
import time
import argparse
import signal

import json
import multiprocessing

from copr.exceptions import CoprException
from copr.exceptions import CoprRequestException

from copr_backend.helpers import BackendConfigReader
from copr_backend.helpers import uses_devel_repo, get_persistent_status, get_auto_prune_status
from copr_backend.frontend import FrontendClient
from copr_backend.createrepo import createrepo

log = multiprocessing.get_logger()

DEF_DAYS = 14
MAX_PROCESS = 50

parser = argparse.ArgumentParser(
        description="Automatically prune copr result directory")
parser.add_argument(
        "--no-mtime-optimization",
        action='store_true',
        help=("Also try to prune repositories where no new builds "
              "have been done for a long time"))


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
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    (stdout, stderr) = process.communicate()
    if process.returncode != 0:
        logerror(stderr)
        raise Exception("Got non-zero return code ({0}) from prunerepo with stderr: {1}".format(process.returncode, stderr))
    return stdout

def run_prunerepo(cmd, chroot_path, username, projectname, projectdir, sub_dir_name, prune_days):
    # ignore the SIGINT otherwise prunerepo will print to broken pipe when Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        result = runcmd(cmd)
        createrepo(path=chroot_path, username=username,
                   projectname=projectname)
        clean_copr(chroot_path, prune_days, verbose=True)
        return result
    except Exception as err:
        logexception(err)
        logerror("Error pruning chroot {}/{}:{}".format(username, projectdir, sub_dir_name))

class Pruner(object):
    def __init__(self, opts, cmdline_opts=None):
        self.opts = opts
        self.prune_days = getattr(self.opts, "prune_days", DEF_DAYS)
        self.chroots = {}
        self.frontend_client = FrontendClient(self.opts, try_indefinitely=True)
        self.mtime_optimization = True
        self.max_processes = getattr(self.opts, "max_prune_processes", MAX_PROCESS)
        self.pool = multiprocessing.Pool(processes=self.max_processes)
        if cmdline_opts:
            self.mtime_optimization = not cmdline_opts.no_mtime_optimization

    def __del__(self):
        # see the warning at
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.Pool
        self.pool.close()
        self.pool.join()

    def run(self):
        response = self.frontend_client.get("chroots-prunerepo-status")
        self.chroots = json.loads(response.content)

        results_dir = self.opts.destdir
        loginfo("Pruning results dir: {} ".format(results_dir))
        user_dir_names, user_dirs = list_subdir(results_dir)

        loginfo("Going to process total number: {} of user's directories".format(len(user_dir_names)))
        loginfo("Going to process user's directories: {}".format(user_dir_names))

        loginfo("--------------------------------------------")
        for username, subpath in zip(user_dir_names, user_dirs):
            loginfo("For user `{}` exploring path: {}".format(username, subpath))
            for projectdir, project_path in zip(*list_subdir(subpath)):
                loginfo("Exploring projectdir `{}` with path: {}".format(projectdir, project_path))
                self.prune_project(project_path, username, projectdir)
                loginfo("--------------------------------------------")

        loginfo("Setting final_prunerepo_done for deactivated chroots")
        chroots_to_prune = []
        for chroot, active in self.chroots.items():
            if not active:
                chroots_to_prune.append(chroot)
        self.frontend_client.post(chroots_to_prune, "final-prunerepo-done")

        self.pool.close()
        self.pool.join()
        loginfo("--------------------------------------------")
        loginfo("Pruning finished")

    def prune_project(self, project_path, username, projectdir):
        loginfo("Going to prune {}/{}".format(username, projectdir))

        projectname = projectdir.split(':', 1)[0]
        loginfo("projectname = {}".format(projectname))

        try:
            if uses_devel_repo(self.opts.frontend_base_url, username, projectname):
                loginfo("Skipped {}/{} since auto createrepo option is disabled"
                          .format(username, projectdir))
                return
            if get_persistent_status(self.opts.frontend_base_url, username, projectname):
                loginfo("Skipped {}/{} since the project is persistent"
                          .format(username, projectdir))
                return
            if not get_auto_prune_status(self.opts.frontend_base_url, username, projectname):
                loginfo("Skipped {}/{} since auto-prunning is disabled for the project"
                          .format(username, projectdir))
                return
        except (CoprException, CoprRequestException) as exception:
            logerror("Failed to get project details for {}/{} with error: {}".format(
                username, projectdir, exception))
            return

        for sub_dir_name in os.listdir(project_path):
            chroot_path = os.path.join(project_path, sub_dir_name)

            if sub_dir_name == 'modules':
                continue

            if not os.path.isdir(chroot_path):
                continue

            if sub_dir_name not in self.chroots:
                loginfo("Final pruning already done for chroot {}/{}:{}".format(username, projectdir, sub_dir_name))
                continue

            if self.mtime_optimization:
                # We only ever remove builds that were done at least
                # 'self.prune_days' ago.  And because we run prunerepo _daily_
                # we know that the candidates for removal (if there are such)
                # are removed about a day after "build_time + self.prune_days".
                touched_before = time.time()-os.stat(chroot_path).st_mtime
                touched_before = touched_before/3600/24 # seconds -> days

                # Because it might happen that prunerepo has some problems to
                # successfully go through the directory for some time (bug, user
                # error, I/O problems...) we rather wait 10 more days till we
                # really start to ignore the directory.
                if touched_before > int(self.prune_days) + 10:
                    loginfo("Skipping {} - not changed for {} days".format(
                        sub_dir_name, touched_before))
                    continue
            cmd = ['prunerepo', '--verbose', '--days', str(self.prune_days), '--nocreaterepo', chroot_path]
            self.pool.apply_async(run_prunerepo,
                                  (cmd, chroot_path, username, projectname,
                                   projectdir, sub_dir_name, self.prune_days),
                                  callback=loginfo, error_callback=logerror)

            # this does not make sense unless max_prune_processes is set to 1
            #loginfo("Pruning done for chroot {}/{}:{}".format(username, projectdir, sub_dir_name))
        #loginfo("Pruning finished for projectdir {}/{}".format(username, projectdir))


def clean_copr(path, days=DEF_DAYS, verbose=True):
    """
    Remove whole copr build dirs if they no longer contain a RPM file
    """
    loginfo("Cleaning COPR repository...")
    for dir_name in os.listdir(path):
        dir_path = os.path.abspath(os.path.join(path, dir_name))

        if not os.path.isdir(dir_path):
            continue
        if not os.path.isfile(os.path.join(dir_path, 'build.info')):
            continue
        if is_rpm_in_dir(dir_path):
            continue
        if time.time() - os.stat(dir_path).st_mtime <= days * 24 * 3600:
            continue

        if verbose:
            loginfo('Removing: ' + dir_path)
        shutil.rmtree(dir_path)

        # also remove the associated log in the main dir
        build_id = os.path.basename(dir_path).split('-')[0]
        buildlog_name = 'build-' + build_id + '.log'
        buildlog_path = os.path.abspath(os.path.join(path, buildlog_name))
        rm_file(os.path.join(path, buildlog_path))


def rm_file(path, verbose=True):
    """
    Remove file given its absolute path
    """
    if verbose:
        loginfo("Removing: "+path)
    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)


def is_rpm_in_dir(path):
    files = os.listdir(path)
    srpm_ex = (".src.rpm", ".nosrc.rpm")
    return any([f for f in files if f.endswith(".rpm") and not f.endswith(srpm_ex)])


def main():
    args = parser.parse_args()
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    pruner = Pruner(BackendConfigReader(config_file).read(), args)
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
