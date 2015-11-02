#!/usr/bin/python

import os
import json
import time
import shutil
import tempfile
import logging
from subprocess import PIPE, Popen, call

from requests import get, post

from .exceptions import PackageImportException, PackageDownloadException, PackageQueryException, GitAndTitoException
from .srpm_import import do_git_srpm_import

from .helpers import FailTypeEnum

log = logging.getLogger(__name__)


class SourceType:
    SRPM_LINK = 1
    SRPM_UPLOAD = 2
    GIT_AND_TITO = 3
    GIT_AND_MOCK = 4


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

        # For SRPM_LINK and SRPM_UPLOAD
        self.package_url = None

        # For GIT_AND_TITO
        self.tito_git_url = None
        self.tito_git_dir = None
        self.tito_git_branch = None
        self.tito_test = None

        # For GIT_AND_MOCK
        self.mock_git_url = None
        self.mock_git_dir = None
        self.mock_git_branch = None


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

        elif task.source_type == SourceType.GIT_AND_TITO:
            task.tito_git_url = task.source_data["git_url"]
            task.tito_git_dir = task.source_data["git_dir"]
            task.tito_git_branch = task.source_data["git_branch"]
            task.tito_test = task.source_data["tito_test"]

        elif task.source_type == SourceType.GIT_AND_MOCK:
            task.mock_git_url = task.source_data["git_url"]
            task.mock_git_dir = task.source_data["git_dir"]
            task.mock_git_branch = task.source_data["git_branch"]

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


class SourceDownloader(object):
    @classmethod
    def get_srpm(cls, task, target_path):
        """
        Download sources from anywhere in any form and save them as SRPM
        :param ImportTask task:
        :param str target_path:
        """
        if task.source_type == SourceType.SRPM_LINK:
            cls._from_srpm_url(task, target_path)

        elif task.source_type == SourceType.SRPM_UPLOAD:
            cls._from_srpm_url(task, target_path)

        elif task.source_type == SourceType.GIT_AND_TITO:
            cls._from_git_and_tito(task, target_path)

        elif task.source_type == SourceType.GIT_AND_MOCK:
            cls._from_git_and_builder(task.source_type, task.mock_git_url, task.mock_git_dir, task.mock_git_branch,
                                      target_path, cls._build_from_mock, task)

        else:
            raise PackageImportException("Got unknown source type: {}".format(task.source_type))

    @classmethod
    def _from_git_and_builder(cls, source_type, git_url, git_dir, git_branch, target_path, builder, task):
        """
        :param ImportTask task:
        :param str target_path:
        :param function builder describe what to do with sources obtained via Git:
        :raises PackageDownloadException:
        """
        tmp = tempfile.mkdtemp()

        # 1. clone the repo
        log.debug("{}: 1. clone".format(source_type))
        cmd = ['git', 'clone', git_url]
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tmp)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("git_clone_failed"))
        if error:
            raise GitAndTitoException(FailTypeEnum("git_clone_failed"))

        # 1b. get dir name
        log.debug("{}: 1b. dir name...".format(source_type))
        cmd = ['ls']
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tmp)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        if error:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        if output and len(output.split()) == 1:
            git_dir_name = output.split()[0]
        else:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        log.debug("   {}".format(git_dir_name))

        git_subdir = "{}/{}/{}".format(tmp, git_dir_name, git_dir)

        # 2. checkout git branch
        log.debug("{}: 2. checkout".format(source_type))
        if git_branch and git_branch != 'master':
            cmd = ['git', 'checkout', git_branch]
            try:
                proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=git_subdir)
                output, error = proc.communicate()
            except OSError as e:
                raise GitAndTitoException(FailTypeEnum("tito_git_checkout_error"))
            if error:
                raise GitAndTitoException(FailTypeEnum("tito_git_checkout_error"))

        # 3. build with ``builder``
        tmp_dest = tempfile.mkdtemp()
        log.debug("{}: 3. build".format(source_type))
        builder(task, git_subdir, tmp_dest)

        # 4. copy srpm to the target destination
        log.debug("{}: 4. get srpm path".format(source_type))
        dest_files = os.listdir(tmp_dest)
        dest_srpms = filter(lambda f: f.endswith(".src.rpm"), dest_files)
        if len(dest_srpms) == 1:
            srpm_name = dest_srpms[0]
        else:
            log.debug("ERROR :( :( :(")
            log.debug("git_subdir: {}".format(git_subdir))
            log.debug("dest_files: {}".format(dest_files))
            log.debug("dest_srpms: {}".format(dest_srpms))
            log.debug("")
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))
        log.debug("   {}".format(srpm_name))
        shutil.copyfile("{}/{}".format(tmp_dest, srpm_name), target_path)

        # 5. delete temps
        log.debug("{}: 5. delete tmp".format(source_type))
        shutil.rmtree(tmp)
        shutil.rmtree(tmp_dest)

    @classmethod
    def _from_git_and_tito(cls, task, target_path):
        """
        Used for GIT_AND_TITO
        :param ImportTask task:
        :param str target_path:
        :raises PackageDownloadException:
        """
        # task.tito_git_url
        # task.tito_git_dir
        # task.tito_git_branch
        # task.tito_test
        tmp = tempfile.mkdtemp()

        # 1. clone the repo
        log.debug("TITO: 1. clone")
        cmd = ['git', 'clone', task.tito_git_url]
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tmp)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("git_clone_failed"))
        if error:
            raise GitAndTitoException(FailTypeEnum("git_clone_failed"))

        # 1b. get dir name
        log.debug("TITO: 1b. dir name...")
        cmd = ['ls']
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tmp)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        if error:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        if output and len(output.split()) == 1:
            git_dir_name = output.split()[0]
        else:
            raise GitAndTitoException(FailTypeEnum("tito_wrong_directory_in_git"))
        log.debug("   {}".format(git_dir_name))

        tito_dir = "{}/{}/{}".format(tmp, git_dir_name, task.tito_git_dir) 

        # 2. checkout git branch
        log.debug("TITO: 2. checkout")
        if task.tito_git_branch and task.tito_git_branch != 'master':
            cmd = ['git', 'checkout', task.tito_git_branch]
            try:
                proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tito_dir)
                output, error = proc.communicate()
            except OSError as e:
                raise GitAndTitoException(FailTypeEnum("tito_git_checkout_error"))
            if error:
                raise GitAndTitoException(FailTypeEnum("tito_git_checkout_error"))

        # 3. build with tito
        tmp_tito = tempfile.mkdtemp()
        log.debug("TITO: 3. build")
        cmd = ['tito', 'build', '-o', tmp_tito, '--srpm']
        if task.tito_test:
            cmd.append('--test')

        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=tito_dir)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))
        if error:
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))

        # 4. copy srpm to the target destination
        log.debug("TITO: 4. get srpm path")
        tito_files = os.listdir(tmp_tito)
        tito_srpms = filter(lambda f: f.endswith(".src.rpm"), tito_files)
        if len(tito_srpms) == 1:
            srpm_name = tito_srpms[0]
        else:
            log.debug("ERROR :( :( :(")
            log.debug("tito_dir: {}".format(tito_dir))
            log.debug("tito_files: {}".format(tito_files))
            log.debug("tito_srpms: {}".format(tito_srpms))
            log.debug("")
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))
        log.debug("   {}".format(srpm_name))
        shutil.copyfile("{}/{}".format(tmp_tito, srpm_name), target_path)

        # 5. delete temps
        log.debug("TITO: 5. delete tmp")
        shutil.rmtree(tmp)
        shutil.rmtree(tmp_tito)

    @classmethod
    def _build_from_tito(cls, task, git_subdir, tmp_dest):
        cmd = ['tito', 'build', '-o', tmp_dest, '--srpm']
        if task.tito_test:
            cmd.append('--test')

        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=git_subdir)
            output, error = proc.communicate()
        except OSError as e:
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))
        if error:
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))

    @classmethod
    def _build_from_mock(cls, task, git_subdir, tmp_dest):

        specs = filter(lambda x: x.endswith(".spec"), os.listdir(git_subdir))
        if len(specs) != 1:
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))

        package_name = specs[0].replace(".spec", "")
        cmd = ['/usr/bin/mock', '-r', 'fedora-22-x86_64',
               '--scm-enable',
               '--scm-option', 'method=git',
               '--scm-option', 'package={}'.format(package_name),
               '--scm-option', 'branch={}'.format(task.mock_git_branch),
               '--scm-option', 'write_tar=True',
               '--scm-option', 'git_get="git clone {}"'.format(task.mock_git_url),
               '--buildsrpm', '--resultdir={}'.format(tmp_dest)]

        try:
            proc = Popen(" ".join(cmd), shell=True, stdout=PIPE, stderr=PIPE, cwd=git_subdir)
            output, error = proc.communicate()
        except OSError as e:
            log.error(error)
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))
        if proc.returncode:
            log.error(error)
            raise GitAndTitoException(FailTypeEnum("tito_srpm_build_error"))

    @classmethod
    def _from_srpm_url(cls, task, target_path):
        """
        Used for SRPM_LINK and SRPM_UPLOAD
        :param ImportTask task:
        :param str target_path:
        :raises PackageDownloadException:
        """
        log.debug("download the package")
        try:
            r = get(task.package_url, stream=True, verify=False)
        except Exception:
            raise PackageDownloadException("Unexpected error during URL fetch: {}"
                                           .format(task.package_url))

        if 200 <= r.status_code < 400:
            try:
                with open(target_path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
            except Exception:
                raise PackageDownloadException("Unexpected error during URL retrieval: {}"
                                               .format(task.package_url))
        else:
            raise PackageDownloadException("Failed to fetch: {} with HTTP status: {}"
                                           .format(task.package_url, r.status_code))


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
        log.debug("Sending back: \n{}".format(json.dumps(data_dict)))
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
            SourceDownloader.get_srpm(task, fetched_srpm_path)
            task.package_name, task.package_version = self.pkg_name_evr(fetched_srpm_path)

            self.before_git_import(task)
            task.git_hash = self.git_import_srpm(task, fetched_srpm_path)
            self.after_git_import()

            log.debug("sending a response - success")
            self.post_back(task.get_dict_for_frontend())

        except PackageImportException:
            log.exception("send a response - failure during import of: {}".format(task.package_url))
            self.post_back_safe({"task_id": task.task_id, "error": "git_import_failed"})

        except PackageDownloadException:
            log.exception("send a response - failure during download of: {}".format(task.package_url))
            self.post_back_safe({"task_id": task.task_id, "error": "srpm_download_failed"})

        except PackageQueryException:
            log.exception("send a response - failure during query of: {}".format(task.package_url))
            self.post_back_safe({"task_id": task.task_id, "error": "srpm_query_failed"})

        except GitAndTitoException as e:
            log.exception("send a response - failure during 'Tito and Git' import of: {}".format(task.tito_git_url))
            log.exception("   ... due to: {}".format(str(e)))
            self.post_back_safe({"task_id": task.task_id, "error": str(e)})

        except Exception:
            log.exception("Unexpected error during package import")
            self.post_back_safe({"task_id": task.task_id, "error": "unknown_error"})

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
