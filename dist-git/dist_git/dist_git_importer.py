#!/usr/bin/python

import os
import json
import time
import shutil
import tempfile
import logging
import datetime
import psutil
from multiprocessing import Process
from subprocess import PIPE, Popen, call

from requests import get, post

from .exceptions import CoprDistGitException, PackageImportException, PackageDownloadException, SrpmBuilderException, \
        SrpmQueryException, GitCloneException, GitWrongDirectoryException, GitCheckoutException, TimeoutException
from .srpm_import import do_git_srpm_import

from .helpers import FailTypeEnum

log = logging.getLogger(__name__)


class SourceType:
    SRPM_LINK = 1
    SRPM_UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6


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

        # For Git based providers (GIT_AND_TITO)
        self.git_url = None
        self.git_branch = None

        # For GIT_AND_TITO
        self.tito_git_dir = None
        self.tito_test = None

        # For MOCK_SCM
        self.mock_scm_type = None
        self.mock_scm_url = None
        self.mock_scm_branch = None
        self.mock_spec = None

        # For PyPI
        self.pypi_package_name = None
        self.pypi_package_version = None
        self.pypi_python_versions = None

        # For RubyGems
        self.gem_name = None

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
            task.git_url = task.source_data["git_url"]
            task.git_branch = task.source_data["git_branch"]
            task.tito_git_dir = task.source_data["git_dir"]
            task.tito_test = task.source_data["tito_test"]

        elif task.source_type == SourceType.MOCK_SCM:
            task.mock_scm_type = task.source_data["scm_type"]
            task.mock_scm_url = task.source_data["scm_url"]
            task.mock_scm_branch = task.source_data["scm_branch"]
            task.mock_spec = task.source_data["spec"]

        elif task.source_type == SourceType.PYPI:
            task.pypi_package_name = task.source_data["pypi_package_name"]
            task.pypi_package_version = task.source_data["pypi_package_version"]
            task.pypi_python_versions = task.source_data["python_versions"]

        elif task.source_type == SourceType.RUBYGEMS:
            task.rubygems_gem_name = task.source_data["gem_name"]

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


class SourceProvider(object):
    """
    Proxy to download sources and save them as SRPM
    """
    def __init__(self, task, target_path):
        """
        :param ImportTask task:
        :param str target_path:
        """
        self.task = task
        self.target_path = target_path

        if task.source_type == SourceType.SRPM_LINK:
            self.provider_class = SrpmUrlProvider
        elif task.source_type == SourceType.SRPM_UPLOAD:
            self.provider_class = SrpmUrlProvider
        elif task.source_type == SourceType.GIT_AND_TITO:
            self.provider_class = GitAndTitoProvider
        elif task.source_type == SourceType.MOCK_SCM:
            self.provider_class = MockScmProvider
        elif task.source_type == SourceType.PYPI:
            self.provider_class = PyPIProvider
        elif task.source_type == SourceType.RUBYGEMS:
            self.provider_class = RubyGemsProvider
        else:
            raise PackageImportException("Got unknown source type: {}".format(task.source_type))
        self.provider = self.provider_class(self.task, self.target_path)

    def get_srpm(self):
        self.provider.get_srpm()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.provider.cleanup()

    def cleanup(self):
        self.provider.cleanup()


class BaseSourceProvider(object):
    def __init__(self, task, target_path):
        self.task = task
        self.target_path = target_path
        self.dir_to_cleanup = [self.target_path]

    def cleanup(self):
        for directory in self.dir_to_cleanup:
            try:
                shutil.rmtree(directory)
            except OSError as e:
                pass #what else we can do? Hopefuly tmpreaper will clean it up
        self.dir_to_cleanup = []

class SrpmBuilderProvider(BaseSourceProvider):
    def __init__(self, task, target_path):
        super(SrpmBuilderProvider, self).__init__(task, target_path)
        self.tmp = tempfile.mkdtemp()
        self.tmp_dest = tempfile.mkdtemp()
        self.dir_to_cleanup.extend([self.tmp, self.tmp_dest])

    def copy(self):
        # 4. copy srpm to the target destination
        log.debug("GIT_BUILDER: 4. get srpm path")
        dest_files = os.listdir(self.tmp_dest)
        dest_srpms = filter(lambda f: f.endswith(".src.rpm"), dest_files)
        if len(dest_srpms) == 1:
            srpm_name = dest_srpms[0]
        else:
            log.debug("tmp_dest: {}".format(self.tmp_dest))
            log.debug("dest_files: {}".format(dest_files))
            log.debug("dest_srpms: {}".format(dest_srpms))
            raise SrpmBuilderException("No srpm files were generated.")
        log.debug("Found srpm: {}".format(srpm_name))
        shutil.copyfile("{}/{}".format(self.tmp_dest, srpm_name), self.target_path)


class GitProvider(SrpmBuilderProvider):
    def __init__(self, task, target_path):
        """
        :param ImportTask task:
        :param str target_path:
        """
        # task.git_url
        # task.git_branch
        super(GitProvider, self).__init__(task, target_path)
        self.git_dir = None

    def get_srpm(self):
        self.clone()
        self.checkout()
        self.build()
        self.copy()

    def clone(self):
        # 1. clone the repo
        log.debug("GIT_BUILDER: 1. clone")
        cmd = ['git', 'clone', self.task.git_url]
        try:
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=self.tmp)
            output, error = proc.communicate()
        except OSError as e:
            raise GitCloneException(str(e))
        if proc.returncode != 0:
            raise GitCloneException(error)

        # 1b. get dir name
        log.debug("GIT_BUILDER: 1b. dir name...")
        try:
            files = os.listdir(self.tmp)
        except OSError as e:
            raise GitWrongDirectoryException(str(e))
        if not files or len(files) != 1:
            raise GitWrongDirectoryException("Could not get name of git directory.")

        git_dir_name = files[0]
        log.debug("Git directory name: {}".format(git_dir_name))
        self.git_dir = "{}/{}".format(self.tmp, git_dir_name)

    def checkout(self):
        # 2. checkout git branch
        log.debug("GIT_BUILDER: 2. checkout")
        if self.task.git_branch and self.task.git_branch != 'master':
            cmd = ['git', 'checkout', self.task.git_branch]
            try:
                proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=self.git_dir)
                output, error = proc.communicate()
            except OSError as e:
                raise GitCheckoutException(str(e))
            if proc.returncode != 0:
                raise GitCheckoutException(error)

    def build(self):
        raise NotImplemented


class GitAndTitoProvider(GitProvider):
    """
    Used for GIT_AND_TITO
    """
    def build(self):
        # task.tito_test
        # task.tito_git_dir
        log.debug("GIT_BUILDER: 3. build via tito")
        cmd = ['tito', 'build', '-o', self.tmp_dest, '--srpm']
        if self.task.tito_test:
            cmd.append('--test')
        git_subdir = "{}/{}".format(self.git_dir, self.task.tito_git_dir)

        log.debug(' '.join(cmd))
        VM.run(cmd, dst_dir=self.tmp_dest, src_dir=git_subdir, cwd=git_subdir)


class MockScmProvider(SrpmBuilderProvider):
    """
    Used for MOCK_SCM
    """
    def get_srpm(self):
        log.debug("Build via Mock")

        package_name = os.path.basename(self.task.mock_spec).replace(".spec", "")
        cmd = ["/usr/bin/mock", "-r", "epel-7-x86_64",
               "--uniqueext", self.task.task_id,
               "--scm-enable",
               "--scm-option", "method={}".format(self.task.mock_scm_type),
               "--scm-option", "package={}".format(package_name),
               "--scm-option", "branch={}".format(self.task.mock_scm_branch),
               "--scm-option", "write_tar=True",
               "--scm-option", "spec={0}".format(self.task.mock_spec),
               "--scm-option", self.scm_option_get(package_name, self.task.mock_scm_branch),
               "--buildsrpm", "--resultdir={}".format(self.tmp_dest)]
        log.debug(' '.join(cmd))

        VM.run(cmd, dst_dir=self.tmp_dest)
        self.copy()

    def scm_option_get(self, package_name, branch):
        return {
            "git": branch and "git_get='git clone --depth 1 --branch {branch} {0} {1}'" or \
                   "git_get='git clone --depth 1 {0} {1}'",
            "svn": "git_get='git svn clone {0} {1}'"
        }[self.task.mock_scm_type].format(self.task.mock_scm_url, package_name, branch=branch)


class PyPIProvider(SrpmBuilderProvider):
    """
    Used for PyPI
    """
    def get_srpm(self):
        log.debug("GIT_BUILDER: 3. build via pyp2rpm")
        cmd = ['pyp2rpm', self.task.pypi_package_name, '--srpm', '-d', self.tmp_dest]

        for i, python_version in enumerate(self.task.pypi_python_versions):
            if i == 0:
                cmd += ['-b', str(python_version)]
            else:
                cmd += ['-p', str(python_version)]

        if self.task.pypi_package_version:
            cmd += ['-v', self.task.pypi_package_version]

        log.debug(' '.join(cmd))

        output, error = VM.run(cmd, dst_dir=self.tmp_dest)

        log.info(output)
        log.info(error)
        self.copy()


class RubyGemsProvider(SrpmBuilderProvider):
    """
    Used for RUBYGEMS
    """
    def get_srpm(self):
        log.debug("BUILDER: 3. build via gem2rpm")

        # @TODO Use -C argument to specify output directory
        # https://github.com/fedora-ruby/gem2rpm/issues/60
        cmd = ["gem2rpm", self.task.rubygems_gem_name.strip(), "--fetch", "--srpm"]
        log.info(' '.join(cmd))
        output, error = VM.run(cmd, dst_dir=self.tmp_dest, cwd=self.tmp_dest)

        if "Empty tag: License" in error:
            raise SrpmBuilderException("{}\n{}\n{}".format(
                error, "Not specifying a license means all rights are reserved; others have no rights to use the code for any purpose.",
                "See http://guides.rubygems.org/specification-reference/#license="))

        log.info(output)
        log.info(error)
        self.copy()


class SrpmUrlProvider(BaseSourceProvider):
    def get_srpm(self):
        """
        Used for SRPM_LINK and SRPM_UPLOAD
        :param ImportTask task:
        :param str target_path:
        :raises PackageDownloadException:
        """
        log.debug("downloading package {0}".format(self.task.package_url))
        try:
            r = get(self.task.package_url, stream=True, verify=False)
        except Exception as e:
            raise PackageDownloadException(str(e))

        if 200 <= r.status_code < 400:
            try:
                with open(self.target_path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
            except Exception as e:
                raise PackageDownloadException(str(e))
        else:
            raise PackageDownloadException("Failed to fetch: {0} with HTTP status: {1}"
                                           .format(self.task.package_url, r.status_code))


class DistGitImporter(object):
    def __init__(self, opts):
        self.is_running = False
        self.opts = opts

        self.get_url = "{}/backend/importing/".format(self.opts.frontend_base_url)
        self.upload_url = "{}/backend/import-completed/".format(self.opts.frontend_base_url)
        self.auth = ("user", self.opts.frontend_auth)
        self.headers = {"content-type": "application/json"}

        self.tmp_root = None

    def try_to_obtain_new_tasks(self, exclude=[], limit=1):
        log.debug("1. Try to get task data")
        try:
            # get the data
            r = get(self.get_url)
            # take the first task
            builds_list = filter(lambda x: x["task_id"] not in exclude, r.json()["builds"])
            if len(builds_list) == 0:
                log.debug("No new tasks to process")
                return

            builds = Filters.get_multiple(builds_list, limit)
            if not builds:
                log.debug("No task meets the criteria to be imported now")
                log.debug("Queued builds: {}".format(builds_list))
                return

            return [ImportTask.from_dict(build, self.opts) for build in builds]
        except Exception as e:
            log.error("Failed acquire new packages for import:")
            log.exception(str(e))
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
            raise SrpmQueryException(str(e))
        if proc.returncode != 0:
            raise SrpmQueryException('Error querying srpm: %s' % error)

        try:
            name, epoch, version, release = output.split(" ")
        except ValueError as e:
            raise SrpmQueryException(str(e))

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
        except Exception as e:
            log.error("Failed to post back to frontend : {}".format(data_dict))
            log.exception(str(e))

    def do_import(self, task):
        """
        :type task: ImportTask
        """
        per_task_log_handler = self.setup_per_task_logging(task)
        log.info("2. Task: {}, importing the package: {}"
                 .format(task.task_id, task.package_url))
        tmp_root = tempfile.mkdtemp()
        fetched_srpm_path = os.path.join(tmp_root, "package.src.rpm")

        provider = SourceProvider(task, fetched_srpm_path)
        try:
            provider.get_srpm()
            task.package_name, task.package_version = self.pkg_name_evr(fetched_srpm_path)

            self.before_git_import(task)
            task.git_hash = self.git_import_srpm(task, fetched_srpm_path)
            self.after_git_import()

            log.debug("sending a response - success")
            self.post_back(task.get_dict_for_frontend())

        except CoprDistGitException as e:
            log.exception("Exception raised during srpm import:")
            self.post_back_safe({"task_id": task.task_id, "error": e.strtype})

        finally:
            provider.cleanup()
            shutil.rmtree(tmp_root, ignore_errors=True)
            self.teardown_per_task_logging(per_task_log_handler)

    def setup_per_task_logging(self, task):
        handler = logging.FileHandler(os.path.join(self.opts.per_task_log_dir, "{0}.log".format(task.task_id)))
        handler.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(handler)
        return handler

    def teardown_per_task_logging(self, handler):
        logging.getLogger('').removeHandler(handler)

    def run(self):
        log.info("DistGitImported initialized")

        VM.build_image()
        pool = Pool(workers=3)
        self.is_running = True
        while self.is_running:
            pool.terminate_timeouted(callback=self.post_back_safe)
            pool.remove_dead()

            if pool.busy:
                time.sleep(self.opts.pool_busy_sleep_time)
                continue

            mb_tasks = self.try_to_obtain_new_tasks(exclude=[w.id for w in pool],
                                                    limit=pool.workers - len(pool))
            if not mb_tasks:
                time.sleep(self.opts.sleep_time)
                continue

            for mb_task in mb_tasks:
                p = Worker(target=self.do_import, args=[mb_task], id=mb_task.task_id, timeout=3600)
                pool.append(p)
                log.info("Starting worker '{}' with task '{}' (timeout={})"
                         .format(p.name, mb_task.task_id, p.timeout))
                p.start()


class Worker(Process):
    def __init__(self, id=None, timeout=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.id = id
        self.timeout = timeout
        self.timestamp = datetime.datetime.now()

    @property
    def timeouted(self):
        return datetime.datetime.now() >= self.timestamp + datetime.timedelta(seconds=self.timeout)


class Pool(list):
    def __init__(self, workers=None, *args, **kwargs):
        super(Pool, self).__init__(*args, **kwargs)
        self.workers = workers

    @property
    def busy(self):
        # There is running job on every core
        return len(self) >= self.workers

    def terminate_timeouted(self, callback):
        for worker in filter(lambda w: w.timeouted, self):
            log.info("Going to terminate worker '{}' with task '{}' due to exceeded timeout {} seconds"
                     .format(worker.name, worker.id, worker.timeout))
            worker.terminate()
            callback({"task_id": worker.id, "error": TimeoutException.strtype})
            log.info("Worker '{}' with task '{}' was terminated".format(worker.name, worker.timeout))

    def remove_dead(self):
        for worker in filter(lambda w: not w.is_alive(), self):
            if worker.exitcode == 0:
                log.info("Worker '{}' finished task '{}'".format(worker.name, worker.id))
            log.info("Removing worker '{}' with task '{}' from pool".format(worker.name, worker.id))
            self.remove(worker)


class Filters(object):
    sources = {
        SourceType.MOCK_SCM: [
            lambda x: psutil.disk_usage("/var/lib/mock")[2] / 1024 / 1024 / 1024 > 2,
        ],
    }

    @classmethod
    def get(cls, builds):
        results = cls.get_multiple(builds, 1)
        return results[0] if results else None

    @classmethod
    def get_multiple(cls, builds, limit):
        results = []
        for build in builds:
            if all([f(build) for f in cls.sources.get(build["source_type"], [])]):
                results.append(build)

            if len(results) >= limit:
                break
        return results


class VM(object):
    hash = None

    @staticmethod
    def run(cmd, dst_dir, src_dir="/tmp", cwd="/"):
        """
        Run command in Virtual Machine (Docker)
        :param cmd: list
        :return: tuple output, error
        """
        try:
            docker_cmd = ["docker", "run",
                          "--privileged",
                          "-v", "{}:{}".format(dst_dir, dst_dir),
                          "-v", "{}:{}".format(src_dir, src_dir),
                          "-w", cwd,
                          VM.hash] + cmd
            log.debug("Running: {}".format(" ".join(docker_cmd)))
            proc = Popen(docker_cmd, stdout=PIPE, stderr=PIPE)
            output, error = proc.communicate()
        except OSError as e:
            raise SrpmBuilderException(str(e))

        if proc.returncode != 0:
            raise SrpmBuilderException(error)

        return output, error

    @staticmethod
    def build_image():
        cmd = ["docker", "build", "-q", os.path.join(os.path.dirname(__file__), "docker")]
        log.debug("Building VM image: {}".format(" ".join(cmd)))
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        output, error = proc.communicate()

        if proc.returncode != 0 or error:
            raise CoprDistGitException(error)

        VM.hash = output.split(":")[1][:12]
        return output
