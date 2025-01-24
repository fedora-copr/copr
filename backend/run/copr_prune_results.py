#!/usr/bin/python3

import logging
import os
import shutil
import sys
import subprocess
import pwd
import time
import argparse

import json
import multiprocessing

from prunerepo.helpers import get_rpms_to_remove

from copr.v3.exceptions import CoprException

from copr_backend.helpers import (
    BackendConfigReader,
    call_copr_repo,
    get_project_info,
    get_redis_logger,
    uses_devel_repo,
)

from copr_backend.frontend import FrontendClient


LOG = multiprocessing.log_to_stderr()
LOG.setLevel(logging.INFO)

DEF_DAYS = 14

parser = argparse.ArgumentParser(
        description="Automatically prune copr result directory")
parser.add_argument(
        "--no-mtime-optimization",
        action='store_true',
        help=("Also try to prune repositories where no new builds "
              "have been done for a long time"))
parser.add_argument(
        "--prune-finalized-chroots",
        action='store_true',
        help=("Also prune chroots that are inactive and we already did "
              "the last prunerepo there, implies --no-mtime-optimization"))
parser.add_argument(
        "--no-threads",
        action="store_true",
        help="Don't use multiprocessing. This is useful for debugging with ipdb")

def list_subdir(path):
    dir_names = [d.name for d in os.scandir(path) if d.is_dir()]
    return dir_names, map(lambda x: os.path.join(path, x), dir_names)

def runcmd(cmd):
    """
    Run given command in a subprocess
    """
    LOG.info('Executing: %s', cmd)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    (stdout, stderr) = process.communicate()
    if process.returncode != 0:
        LOG.error(stderr)
        raise Exception("Got non-zero return code ({0}) from prunerepo with stderr: {1}".format(process.returncode, stderr))
    return stdout


def arg_max_splitter(args, window):
    """
    Split the ARGS into a list of SUB-ARGS with at most WINDOW items.
    """
    length = len(args)
    i = 0
    while i*window < length:
        yield args[i*window:(i+1)*window]
        i += 1

def run_prunerepo(chroot_path, username, projectdir, sub_dir_name, prune_days,
                  appstream):
    """
    Running prunerepo in background worker.  We don't check the return value, so
    the best we can do is that we return useful success/error message that will
    be logged by parent process.
    """
    try:
        LOG.info("Pruning of %s/%s/%s started", username, projectdir, sub_dir_name)

        repodata = os.path.join(chroot_path, "repodata")
        if not os.path.exists(repodata):
            LOG.info("Recreating missing repodata for %s/%s/%s",
                     username, projectdir, sub_dir_name)
            call_copr_repo(directory=chroot_path, logger=LOG, appstream=appstream)

        all_rpms = get_rpms_to_remove(chroot_path, days=prune_days, log=LOG)

        # See https://github.com/fedora-copr/copr/issues/1817 for more info
        # about reasoning, but here comes TL;DR:
        #
        # The call_copr_repo() calls `copr-repo --rpms-to-remove RPM
        # --rpms-to-remove RPM ...` command.  `copr-repo` then calls
        # `createrepo_c --delete RPM --delete RPM`.  The example enormous
        # project has name average RPM length of 76.45 characters.  So we
        # empirically tested that we can correctly execute this command:
        #
        #   subprocess.call(["/bin/echo"] + ["--rpms-to-remove", "x"*77] * 18867)
        #
        # From this perspective, using a limit with roughly half of it should
        # give the system stack enough space for other nuances.  The limit is
        # big enough, after not cleaning the enormous project for months or
        # maybe years, we accumulated 100k packages, meaning that the first
        # run_prunerepo() call will only do a few calls to `call_copr_repo()`,
        # and then we'll rarely hit the limit.
        for rpms in arg_max_splitter(all_rpms, window=9000):
            LOG.info("Going to remove %s RPMs in %s", len(rpms), chroot_path)
            call_copr_repo(directory=chroot_path, rpms_to_remove=rpms,
                           logger=LOG, appstream=appstream)
        clean_copr(chroot_path, prune_days, verbose=True)
    except Exception:  # pylint: disable=broad-except
        LOG.exception("Error pruning chroot %s/%s/%s", username, projectdir,
                      sub_dir_name)

    LOG.info("Pruning finished for projectdir %s/%s/%s",
             username, projectdir, sub_dir_name)

class Pruner(object):
    # pylint: disable=too-many-instance-attributes

    def __init__(self, opts, cmdline_opts=None):
        self.opts = opts
        self.prune_days = getattr(self.opts, "prune_days", DEF_DAYS)
        self.chroots = {}
        self.frontend_client = FrontendClient(self.opts, try_indefinitely=True,
                                              logger=LOG)
        self.mtime_optimization = True
        self.prune_finalized_chroots = False
        self.no_threads = False
        self.workers = getattr(self.opts, "prune_workers", None)
        self.pool = multiprocessing.Pool(processes=self.workers)
        if cmdline_opts:
            self.mtime_optimization = not cmdline_opts.no_mtime_optimization
            if cmdline_opts.prune_finalized_chroots:
                self.prune_finalized_chroots = True
                # We have to disable mtime optimizations because otherwise we
                # would skip all the old chroots because probably nobody touched
                # them for a very long time.
                self.mtime_optimization = False

            if cmdline_opts.no_threads:
                self.no_threads = True

    def run(self):
        response = self.frontend_client.get("chroots-prunerepo-status")
        self.chroots = json.loads(response.content)

        results_dir = self.opts.destdir
        LOG.info("Pruning results dir: %s", results_dir)
        user_dir_names, user_dirs = list_subdir(results_dir)

        LOG.info("Going to process total number: %s of user's directories", len(user_dir_names))
        LOG.info("Going to process user's directories: %s", user_dir_names)

        LOG.info("--------------------------------------------")
        for username, subpath in zip(user_dir_names, user_dirs):
            LOG.info("For user '%s' exploring path: %s", username, subpath)
            for projectdir, project_path in zip(*list_subdir(subpath)):
                LOG.info("Exploring projectdir '%s' with path: %s", projectdir, project_path)
                self.prune_project(project_path, username, projectdir)
                LOG.info("--------------------------------------------")


        LOG.info("Pruning tasks are delegated to background workers, waiting.")
        self.pool.close()
        self.pool.join()

        LOG.info("Checking if final_prunerepo_done needs to be set")
        chroots_finalized = []
        for chroot, info in self.chroots.items():
            if info["final_prunerepo_done"]:
                # no need to re-finalize on FE
                continue
            if info["active"]:
                # This chroot can still get new builds
                continue
            chroots_finalized.append(chroot)
        if chroots_finalized:
            LOG.info("Setting final_prunerepo_done for deactivated chroots: %s",
                     chroots_finalized)
            self.frontend_client.post("final-prunerepo-done", chroots_finalized)

        LOG.info("--------------------------------------------")

    def should_run_in_chroot(self, username, projectdir, chroot_name):
        """
        Return False if we think that it doesn't make much sense to re-run the
        repo cleanup scripts against this chroot (because nothing could have
        happened since the previous run).
        """
        if chroot_name not in self.chroots:
            if chroot_name != "srpm-builds":
                LOG.error("Wrong chroot name %s/%s:%s",
                          username, projectdir, chroot_name)
            return False

        info = self.chroots[chroot_name]
        if info["final_prunerepo_done"]:
            if self.prune_finalized_chroots:
                LOG.info("Re-running prunerepo in finalized %s/%s:%s",
                         username, projectdir, chroot_name)
                return True
            LOG.info("Final pruning already done for chroot %s/%s:%s",
                     username, projectdir, chroot_name)
            return False

        return True

    def prune_project(self, project_path, username, projectdir):
        LOG.info("Going to prune %s/%s", username, projectdir)

        projectname = projectdir.split(':', 1)[0]
        LOG.info("projectname = %s", projectname)

        appstream = False
        try:
            project_info = get_project_info(self.opts.frontend_base_url,
                                            username, projectname)

            appstream = project_info.get("appstream", False)

            if uses_devel_repo(self.opts.frontend_base_url, username,
                               projectname, project_info):
                LOG.info("Skipped %s/%s since auto createrepo option is disabled",
                         username, projectdir)
                return

            if bool(project_info.get("persistent", True)):
                LOG.info("Skipped %s/%s since the project is persistent",
                         username, projectdir)
                return

            if not bool(project_info.get("auto_prune", True)):
                LOG.info("Skipped %s/%s since auto-prunning is disabled for the project",
                         username, projectdir)
                return
        except CoprException as exception:
            LOG.error("Failed to get project details for %s/%s with error: %s",
                      username, projectdir, exception)
            return

        for sub_dir_name_entry in os.scandir(project_path):
            if not sub_dir_name_entry.is_dir():
                continue

            sub_dir_name = sub_dir_name_entry.name
            if sub_dir_name == 'modules':
                continue

            chroot_path = os.path.join(project_path, sub_dir_name)

            if not self.should_run_in_chroot(username, projectdir, sub_dir_name):
                continue

            if self.mtime_optimization:
                # We only ever remove builds that were done at least
                # 'self.prune_days' ago.  And because we run prunerepo _daily_
                # we know that the candidates for removal (if there are such)
                # are removed about a day after "build_time + self.prune_days".
                touched_before = time.time()-sub_dir_name_entry.stat().st_mtime
                touched_before = touched_before/3600/24 # seconds -> days

                # Because it might happen that prunerepo has some problems to
                # successfully go through the directory for some time (bug, user
                # error, I/O problems...) we rather wait 10 more days till we
                # really start to ignore the directory.
                if touched_before > int(self.prune_days) + 10:
                    LOG.info("Skipping %s - not changed for %s days",
                             sub_dir_name, touched_before)
                    continue

            args = [chroot_path, username, projectdir, sub_dir_name,
                    self.prune_days, appstream]
            self.maybe_async(run_prunerepo, args)

    def maybe_async(self, func, args):
        """
        If multiprocessing support is enabled, run `func` in a separate process,
        otherwise simply call the `func`.
        """
        if self.no_threads:
            func(*args)
        else:
            self.pool.apply_async(func, args)


def clean_copr(path, days=DEF_DAYS, verbose=True):
    """
    Remove whole copr build dirs if they no longer contain a RPM file
    """
    LOG.info("Cleaning COPR repository %s", path)
    for dir_name_entry in os.scandir(path):
        if not dir_name_entry.is_dir():
            continue
        dir_path = os.path.abspath(os.path.join(path, dir_name_entry.name))
        if not os.path.isfile(os.path.join(dir_path, 'build.info')):
            continue
        if is_rpm_in_dir(dir_path):
            continue

        # Note that deleting some rpm files from the directory by
        # run_prunerepo() actually bumps the st_mtime of the directory.  So we
        # keep the directory here at least one another period after the last RPM
        # removal.
        if time.time() - dir_name_entry.stat().st_mtime <= days * 24 * 3600:
            continue

        if verbose:
            LOG.info('Removing: %s', dir_path)
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
        LOG.info("Removing: %s", path)
    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)


def is_rpm_in_dir(path):
    files = os.scandir(path)
    srpm_ex = (".src.rpm", ".nosrc.rpm")
    return any(f.name for f in files if f.name.endswith(".rpm") and not f.name.endswith(srpm_ex))


def redirect_logging(opts):
    """
    Redirect all logging to RedisLogHandler using BackendConfigReader options
    """
    global LOG  # pylint: disable=global-statement
    LOG = get_redis_logger(opts, "copr_prune_results", "pruner")


def main():
    args = parser.parse_args()
    config_file = os.environ.get("BACKEND_CONFIG", "/etc/copr/copr-be.conf")
    opts = BackendConfigReader(config_file).read()
    redirect_logging(opts)
    pruner = Pruner(opts, args)
    try:
        pruner.run()
    except Exception as e:
        LOG.exception(e)

if __name__ == "__main__":
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        main()
