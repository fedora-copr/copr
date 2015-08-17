#!/usr/bin/python

import os
import json
import time
from urllib import urlretrieve
import shutil
import tempfile
import logging
from subprocess import PIPE, Popen

from requests import get, post

# pyrpkg uses os.getlogin(). It requires tty which is unavailable when we run this script as a daemon
# very dirty solution for now
import pwd
import sys
from .exceptions import PackageImportException, PackageDownloadException, PackageQueryException
from .srpm_import import do_git_srpm_import

os.getlogin = lambda: pwd.getpwuid(os.getuid())[0]
# monkey patch end

from subprocess import call

from helpers import DistGitConfigReader

log = logging.getLogger(__name__)


class SourceType:
    SRPM_LINK = 1
    SRPM_UPLOAD = 2


class ImportTask(object):
    def __init__(self):

        self.task_id = None
        self.user = None
        self.project = None
        self.branch = None

        self.source_type = None
        self.source_json = None
        self.source_data = None

        self.package_name = None
        self.package_version = None
        self.git_hash = None

        self.package_url = None

    @property
    def reponame(self):
        if any(x is None for x in [self.user, self.project, self.package_name]):
            return None
        else:
            return "{}/{}/{}".format(self.user, self.project, self.package_name)

    @staticmethod
    def from_dict(dict_data, opts):
        task = ImportTask()

        task.task_id = dict_data["task_id"]
        task.user = dict_data["user"]
        task.project = dict_data["project"]

        task.branch = dict_data["branch"]
        task.source_type = dict_data["source_type"]
        task.source_json = dict_data["source_json"]
        task.source_data = json.loads(dict_data["source_json"])

        if task.source_type == SourceType.SRPM_LINK:
            task.package_url = json.loads(task.source_json)["url"]

        elif task.source_type == SourceType.SRPM_UPLOAD:
            json_tmp = task.source_data["tmp"]
            json_pkg = task.source_data["pkg"]
            task.package_url = "{}/tmp/{}/{}".format(opts.frontend_base_url, json_tmp, json_pkg)

        else:
            raise PackageImportException("Got unknown source type: {}".format(task.source_type))

        return task

    def get_dict_for_frontend(self):
        return {
            "task_id": self.task_id,
            "pkg_name": self.package_name,
            "pkg_version": self.package_version,
            "repo_name": self.reponame,
            "git_hash": self.git_hash
        }


class DistGitImporter(object):
    def __init__(self, opts):
        self.is_running = False
        self.opts = opts

        self.get_url = "{}/backend/importing/".format(self.opts.frontend_base_url)
        self.upload_url = "{}/backend/import-completed/".format(self.opts.frontend_base_url)
        self.auth = ("user", self.opts.frontend_auth)
        self.headers = {"content-type": "application/json"}

        self.tmp_root = None

    def try_to_obtain_new_task(self):
        log.debug("1. Try to get task data")
        try:
            # get the data
            r = get(self.get_url)
            # take the first task
            builds_list = r.json()["builds"]
            if len(builds_list) == 0:
                log.debug("No new tasks to process")
                return
            return ImportTask.from_dict(builds_list[0], self.opts)
        except Exception:
            log.exception("Failed acquire new packages for import")
        return

    @staticmethod
    def fetch_srpm(task, fetched_srpm_path):
        log.debug("download the package")
        try:
            urlretrieve(task.package_url, fetched_srpm_path)
        except IOError:
            raise PackageDownloadException()

    def git_import_srpm(self, task, filepath):
        """
        Imports a source rpm file into local dist git.
        Repository name is in the Copr Style: user/project/package
        filepath is a srpm file locally downloaded somewhere

        :type task: ImportTask
        """
        log.debug("importing srpm into the dist-git")

        tmp = tempfile.mkdtemp()
        try:
            return do_git_srpm_import(self.opts, filepath, task, tmp)
        finally:
            shutil.rmtree(tmp)

    @staticmethod
    def pkg_name_evr(srpm_path):
        """
        Queries a package for its name and evr (epoch:version-release)
        """
        log.debug("Verifying packagage, getting  name and version.")
        cmd = ['rpm', '-qp', '--nosignature', '--qf', '%{NAME} %{EPOCH} %{VERSION} %{RELEASE}', srpm_path]
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            output, error = proc.communicate()
        except OSError as e:
            raise PackageQueryException(e)
        if error:
            raise PackageQueryException('Error querying srpm: %s' % error)

        try:
            name, epoch, version, release = output.split(" ")
        except ValueError as e:
            raise PackageQueryException(e)

        # Epoch is an integer or '(none)' if not set
        if epoch.isdigit():
            evr = "{}:{}-{}".format(epoch, version, release)
        else:
            evr = "{}-{}".format(version, release)

        return name, evr

    def after_git_import(self):
        log.debug("refreshing cgit listing")
        call(["/usr/share/dist-git/cgit_pkg_list.sh", self.opts.cgit_pkg_list_location])

    @staticmethod
    def before_git_import(task):
        log.debug("make sure repos exist: {}".format(task.reponame))
        call(["/usr/share/dist-git/git_package.sh", task.reponame])
        call(["/usr/share/dist-git/git_branch.sh", task.branch, task.reponame])

    def post_back(self, data_dict):
        """
        Could raise error related to networkd connection
        """
        return post(self.upload_url, auth=self.auth, data=json.dumps(data_dict), headers=self.headers)

    def post_back_safe(self, data_dict):
        """
        Ignores any error
        """
        try:
            return self.post_back(data_dict)
        except Exception:
            log.exception("Failed to post back to frontend : {}".format(data_dict))

    def do_import(self, task):
        """
        :type task: ImportTask
        """
        log.info("2. Task: {}, importing the package: {}"
                 .format(task.task_id, task.package_url))
        tmp_root = tempfile.mkdtemp()
        fetched_srpm_path = os.path.join(tmp_root, "package.src.rpm")

        try:
            self.fetch_srpm(task, fetched_srpm_path)
            task.package_name, task.package_version = self.pkg_name_evr(fetched_srpm_path)

            self.before_git_import(task)
            task.git_hash = self.git_import_srpm(task, fetched_srpm_path)
            self.after_git_import()

            log.debug("sending a response - success")
            self.post_back(task.get_dict_for_frontend())

        except (PackageImportException, PackageDownloadException, PackageQueryException):
            log.exception("send a response - failure during import of: {}".format(task.package_url))
            self.post_back_safe({"task_id": task.task_id, "error": "error"})

        except Exception:
            log.exception("Unexpected error during package import")
            self.post_back_safe({"task_id": task.task_id, "error": "error"})

        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def run(self):
        log.info("DistGitImported initialized")

        self.is_running = True
        while self.is_running:
            mb_task = self.try_to_obtain_new_task()
            if mb_task is None:
                time.sleep(self.opts.sleep_time)
            else:
                self.do_import(mb_task)
