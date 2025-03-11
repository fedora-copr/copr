import json
import os
import os.path
import shutil
import time
import traceback
import base64

from distutils.dir_util import copy_tree
from distutils.errors import DistutilsFileError
from urllib.request import urlretrieve
from copr.exceptions import CoprRequestException
from requests import RequestException
from munch import Munch

import modulemd_tools.yaml

from copr_common.rpm import splitFilename
from copr_common.enums import ActionTypeEnum, BackendResultEnum, StorageEnum
from copr_common.worker_manager import WorkerManager
from copr_common.lock import lock

from copr_backend.worker_manager import BackendQueueTask
from copr_backend.storage import storage_for_enum, BackendStorage, PulpStorage

from .sign import create_user_keys, CoprKeygenRequestError
from .exceptions import CreateRepoError, CoprSignError, FrontendClientException
from .helpers import (get_redis_logger, silent_remove, ensure_dir_exists,
                      get_chroot_arch, format_filename,
                      call_copr_repo, copy2_but_hardlink_rpms)
from .sign import sign_rpms_in_dir, unsign_rpms_in_dir, get_pubkey


class Action(object):
    """ Object to send data back to fronted

    :param copr_backend.callback.FrontendCallback frontent_callback:
        object to post data back to frontend

    :param destdir: filepath with build results

    :param dict action: dict-like object with action task

    Expected **action** keys:

        - action_type: main field determining what action to apply
        # TODO: describe actions

    """

    @classmethod
    def create_from(cls, opts, action, log=None):
        action_class = cls.get_action_class(action)
        return action_class(opts, action, log)

    @classmethod
    def get_action_class(cls, action):
        action_type = action["action_type"]
        action_class = {
            ActionTypeEnum("legal-flag"): LegalFlag,
            ActionTypeEnum("createrepo"): Createrepo,
            ActionTypeEnum("update_comps"): CompsUpdate,
            ActionTypeEnum("gen_gpg_key"): GenerateGpgKey,
            ActionTypeEnum("rawhide_to_release"): RawhideToRelease,
            ActionTypeEnum("fork"): Fork,
            ActionTypeEnum("build_module"): BuildModule,
            ActionTypeEnum("remove_dirs"): RemoveDirs,
        }.get(action_type, None)

        if action_type == ActionTypeEnum("delete"):
            object_type = action["object_type"]
            action_class = {
                "copr": DeleteProject,
                "build": DeleteBuild,
                "builds": DeleteMultipleBuilds,
                "chroot": DeleteChroot,
            }.get(object_type, action_class)

        if not action_class:
            raise ValueError("Unexpected action type: {}".format(action))
        return action_class

    # TODO: get more form opts, decrease number of parameters
    def __init__(self, opts, action, log=None):

        self.opts = opts
        self.data = action

        self.ext_data = json.loads(action.get("data", "{}"))

        self.destdir = self.opts.destdir
        self.front_url = self.opts.frontend_base_url
        self.results_root_url = self.opts.results_baseurl

        self.log = log if log else get_redis_logger(self.opts, "backend.actions", "actions")

        self.storage = None
        if isinstance(self.ext_data, dict):
            enum = self.ext_data.get("storage", StorageEnum.backend)
            owner = self.ext_data.get("ownername")
            project = self.ext_data.get("projectname")
            devel = self.ext_data.get("devel")
            appstream = self.ext_data.get("appstream")
            args = [owner, project, appstream, devel, self.opts, self.log]
            self.storage = storage_for_enum(enum, *args)

            # Even though we already have `self.storage` which uses an
            # appropriate storage for the project (e.g. Pulp), the project
            # still has some data on backend (logs, srpm-builds chroot, etc).
            # Many actions need to be performed on `self.storage` and
            # `self.backend_storage` at the same time
            self.backend_storage = storage_for_enum(StorageEnum.backend, *args)

    def __str__(self):
        return "<{}(Action): {}>".format(self.__class__.__name__, self.data)

    def run(self):
        """
        This is an abstract class, implement this function for specific actions
        in their own classes
        """
        raise NotImplementedError()


class LegalFlag(Action):
    def run(self):
        self.log.debug("Action legal-flag: ignoring")


class Createrepo(Action):
    def run(self):
        self.log.info("Action createrepo")
        project_dirnames = self.ext_data["project_dirnames"]
        chroots = self.ext_data["chroots"]
        result = BackendResultEnum("success")

        for project_dirname in project_dirnames:
            for chroot in chroots:
                success = self.storage.init_project(project_dirname, chroot)
                if not success:
                    result = BackendResultEnum("failure")

        if isinstance(self.storage, PulpStorage):
            self.add_http_redirect()

        return result

    def add_http_redirect(self):
        """
        Create a HTTP redirect for this project.  See:
        https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/backend/templates/lighttpd/pulp-redirect.lua.j2
        """
        path = "/var/lib/copr/pulp-redirect.txt"
        fullname = "{0}/{1}".format(self.storage.owner, self.storage.project)
        try:
            with open(path, "r", encoding="utf-8") as fp:
                projects = fp.read().splitlines()

            if fullname in projects:
                return

            lockdir = "/var/lock/copr-backend"
            with lock(path, lockdir=lockdir, timeout=-1, log=self.log):
                with open(path, "a", encoding="utf-8") as fp:
                    print(fullname, file=fp)

        except FileNotFoundError:
            # Ignoring because this Copr instance doesn't need redirects
            pass


class GPGMixin(object):
    def generate_gpg_key(self, ownername, projectname):
        if self.opts.do_sign is False:
            # skip key creation, most probably sign component is unused
            return True
        try:
            create_user_keys(ownername, projectname, self.opts)
            return True
        except CoprKeygenRequestError as e:
            self.log.exception(e)
            return False


class Fork(Action, GPGMixin):
    def run(self):
        sign = self.opts.do_sign
        self.log.info("Action fork %s", self.data["object_type"])
        data = json.loads(self.data["data"])
        old_path = os.path.join(self.destdir, self.data["old_value"])
        new_path = os.path.join(self.destdir, self.data["new_value"])
        builds_map = json.loads(self.data["data"])["builds_map"]

        if not os.path.exists(old_path):
            self.log.info("Source copr directory doesn't exist: %s", old_path)
            result = BackendResultEnum("failure")
            return result

        try:
            ensure_dir_exists(new_path, self.log)
            pubkey_path = os.path.join(new_path, "pubkey.gpg")

            if sign:
                # Generate brand new gpg key.
                self.generate_gpg_key(data["user"], data["copr"])
                # Put the new public key into forked build directory.
                get_pubkey(data["user"], data["copr"], self.log, self.opts.sign_domain, pubkey_path)

            chroot_paths = set()
            for chroot, src_dst_dir in builds_map.items():

                if not chroot or not src_dst_dir:
                    continue

                for old_dir_name, new_dir_name in src_dst_dir.items():
                    src_dir, dst_dir = old_dir_name, new_dir_name

                    if not src_dir or not dst_dir:
                        continue

                    old_chroot_path = os.path.join(old_path, chroot)
                    new_chroot_path = os.path.join(new_path, chroot)
                    chroot_paths.add(new_chroot_path)

                    src_path = os.path.join(old_chroot_path, src_dir)
                    dst_path = os.path.join(new_chroot_path, dst_dir)

                    ensure_dir_exists(dst_path, self.log)

                    try:
                        copy_tree(src_path, dst_path)
                    except DistutilsFileError as e:
                        self.log.error(str(e))
                        continue

                    # Drop old signatures coming from original repo and re-sign.
                    unsign_rpms_in_dir(dst_path, opts=self.opts, log=self.log)
                    if sign:
                        sign_rpms_in_dir(data["user"], data["copr"], dst_path,
                                         chroot, opts=self.opts, log=self.log)

                    self.log.info("Forked build %s as %s", src_path, dst_path)

            result = BackendResultEnum("success")
            for chroot_path in chroot_paths:
                if not call_copr_repo(chroot_path, logger=self.log):
                    result = BackendResultEnum("failure")

        except (CoprSignError, CreateRepoError, CoprRequestException, IOError) as ex:
            self.log.error("Failure during project forking")
            self.log.error(str(ex))
            self.log.error(traceback.format_exc())
            result = BackendResultEnum("failure")
        return result


class DeleteProject(Action):
    def run(self):
        self.log.debug("Action delete copr")
        project_dirnames = self.ext_data["project_dirnames"]

        if not self.storage.owner:
            self.log.error("Received empty ownername!")
            return BackendResultEnum("failure")

        for dirname in project_dirnames:
            if not dirname:
                self.log.warning("Received empty dirname!")
                continue
            self.storage.delete_project(dirname)
            if not isinstance(self.storage, BackendStorage):
                self.backend_storage.delete_project(dirname)

        return BackendResultEnum("success")


class CompsUpdate(Action):
    def run(self):
        self.log.debug("Action comps update")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        chroot = ext_data["chroot"]
        url_path = ext_data["url_path"]

        remote_comps_url = self.opts.frontend_base_url + url_path
        self.log.info(remote_comps_url)

        path = os.path.join(self.destdir, ownername, projectname, chroot)
        ensure_dir_exists(path, self.log)
        local_comps_path = os.path.join(path, "comps.xml")
        result = BackendResultEnum("success")
        if not ext_data.get("comps_present", True):
            silent_remove(local_comps_path)
            self.log.info("deleted comps.xml for %s/%s/%s from %s ",
                          ownername, projectname, chroot, remote_comps_url)
        else:
            try:
                urlretrieve(remote_comps_url, local_comps_path)
                self.log.info("saved comps.xml for %s/%s/%s from %s ",
                              ownername, projectname, chroot, remote_comps_url)
            except Exception:
                self.log.exception("Failed to update comps from %s at location %s",
                                   remote_comps_url, local_comps_path)
                result = BackendResultEnum("failure")
        return result


class DeleteMultipleBuilds(Action):
    def run(self):
        self.log.debug("Action delete multiple builds.")

        # == EXAMPLE DATA ==
        # ownername: @copr
        # projectname: testproject
        # project_dirnames:
        #   testproject:pr:10:
        #     srpm-builds: [00849545, 00849546]
        #     fedora-30-x86_64: [00849545-example, 00849545-foo]
        #   [...]

        project_dirnames = self.ext_data["project_dirnames"]
        build_ids = self.ext_data["build_ids"]

        result = BackendResultEnum("success")
        for project_dirname, chroot_builddirs in project_dirnames.items():
            args = [project_dirname, chroot_builddirs, build_ids]
            success = self.storage.delete_builds(*args)

            if not isinstance(self.storage, BackendStorage):
                success = self.backend_storage.delete_builds(*args) and success

            if not success:
                result = BackendResultEnum("failure")
        return result


class DeleteBuild(Action):
    def run(self):
        self.log.info("Action delete build.")

        # == EXAMPLE DATA ==
        # ownername: @copr
        # projectname: TEST1576047114845905086Project10Fork
        # project_dirname: TEST1576047114845905086Project10Fork:pr:12
        # chroot_builddirs:
        #   srpm-builds: [00849545]
        #   fedora-30-x86_64: [00849545-example]

        valid = "object_id" in self.data
        keys = {"ownername", "projectname", "project_dirname",
                "chroot_builddirs", "appstream"}
        for key in keys:
            if key not in self.ext_data:
                valid = False
                break

        if not valid:
            self.log.exception("Invalid action data")
            return BackendResultEnum("failure")

        args = [
            self.ext_data["project_dirname"],
            self.ext_data["chroot_builddirs"],
            [self.data['object_id']],
        ]
        success = self.storage.delete_builds(*args)
        if not isinstance(self.storage, BackendStorage):
            success = self.backend_storage.delete_builds(*args) and success
        return BackendResultEnum("success" if success else "failure")


class DeleteChroot(Action):
    def run(self):
        self.log.info("Action delete project chroot.")
        chroot = self.ext_data["chrootname"]
        self.storage.delete_repository(chroot)
        return BackendResultEnum("success")


class GenerateGpgKey(Action, GPGMixin):
    def run(self):
        ext_data = json.loads(self.data["data"])
        self.log.info("Action generate gpg key: %s", ext_data)

        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]

        success = self.generate_gpg_key(ownername, projectname)
        return BackendResultEnum("success") if success else BackendResultEnum("failure")


class RawhideToRelease(Action):
    def run(self):
        data = json.loads(self.data["data"])
        appstream = data["appstream"]
        try:
            chrootdir = os.path.join(self.opts.destdir, data["ownername"],
                                     data["copr_dir"], data["dest_chroot"])
            if not os.path.exists(chrootdir):
                self.log.info("Create directory: %s", chrootdir)
                os.makedirs(chrootdir)

            for build in data["builds"]:
                srcdir = os.path.join(self.opts.destdir, data["ownername"],
                                      data["copr_dir"], data["rawhide_chroot"], build)
                if os.path.exists(srcdir):
                    destdir = os.path.join(chrootdir, build)

                    # We can afford doing hardlinks in this case because the
                    # RPMs are not modified at all (contrary to "project
                    # forking", where we have to re-sign the files).
                    self.log.info("Copying directory (link RPMs): %s -> %s",
                                  srcdir, destdir)
                    shutil.copytree(srcdir, destdir,
                                    copy_function=copy2_but_hardlink_rpms)
                    with open(os.path.join(destdir, "build.info"), "a") as f:
                        f.write("\nfrom_chroot={}".format(data["rawhide_chroot"]))
            return self._createrepo_repeatedly(chrootdir, appstream)

        # pylint: disable=broad-except
        except Exception:
            self.log.exception("Unexpected error when forking from rawhide")
            return BackendResultEnum("failure")

    def _createrepo_repeatedly(self, chrootdir, appstream):
        for i in range(5):
            if call_copr_repo(chrootdir, appstream=appstream, logger=self.log):
                return BackendResultEnum("success")
            self.log.error("Createrepo failed, trying again #%s", i)
            time.sleep(10)
        return BackendResultEnum("failure")


class BuildModule(Action):
    def run(self):
        result = BackendResultEnum("success")
        try:
            data = json.loads(self.data["data"])
            ownername = data["ownername"]
            projectname = data["projectname"]
            chroots = data["chroots"]
            project_path = os.path.join(self.opts.destdir, ownername, projectname)
            appstream = data["appstream"]

            mmd_yaml = base64.b64decode(data["modulemd_b64"]).decode("utf-8")
            mmd_yaml = modulemd_tools.yaml.upgrade(mmd_yaml, 2)
            self.log.info("%s", mmd_yaml)

            for chroot in chroots:
                arch = get_chroot_arch(chroot)
                mmd_yaml = modulemd_tools.yaml.update(mmd_yaml, arch=arch)
                artifacts = set()
                srcdir = os.path.join(project_path, chroot)

                # This should be dealt with in the `modulemd_tools` library
                mmd = modulemd_tools.yaml._yaml2stream(mmd_yaml)
                module_tag = "{}+{}-{}-{}".format(chroot, mmd.get_module_name(),
                                                  (mmd.get_stream_name() or ''),
                                                  (str(mmd.get_version()) or '1'))

                module_relpath = os.path.join(module_tag, "latest", arch)
                destdir = os.path.join(project_path, "modules", module_relpath)

                if os.path.exists(destdir):
                    self.log.warning("Module %s already exists. Omitting.", destdir)
                else:
                    # We want to copy just the particular module builds
                    # into the module destdir, not the whole chroot
                    os.makedirs(destdir)
                    prefixes = ["{:08d}-".format(x) for x in data["builds"]]
                    dirs = [d.name for d in os.scandir(srcdir) if d.name.startswith(tuple(prefixes))]
                    for folder in dirs:
                        shutil.copytree(os.path.join(srcdir, folder), os.path.join(destdir, folder))
                        self.log.info("Copy directory: %s as %s",
                                      os.path.join(srcdir, folder), os.path.join(destdir, folder))

                        for folder_entry in os.scandir(os.path.join(destdir, folder)):
                            f = folder_entry.name
                            if not f.endswith(".rpm") or f.endswith(".src.rpm"):
                                continue
                            artifact = format_filename(zero_epoch=True, *splitFilename(f))
                            artifacts.add(artifact)

                    mmd_yaml = modulemd_tools.yaml.update(mmd_yaml, rpms_nevras=artifacts)
                    self.log.info("Module artifacts: %s", artifacts)
                    modulemd_tools.yaml.dump(mmd_yaml, destdir)
                    if not call_copr_repo(destdir, appstream=appstream, logger=self.log):
                        result = BackendResultEnum("failure")

        except Exception:
            self.log.exception("handle_build_module failed")
            result = BackendResultEnum("failure")

        return result


class RemoveDirs(Action):
    """
    Delete outdated CoprDir instances.  Frontend gives us only a list of
    sub-directories to remove.
    """
    def _run_internal(self):
        copr_dirs = json.loads(self.data["data"])
        for copr_dir in copr_dirs:
            assert len(copr_dir.split('/')) == 2
            assert ':pr:' in copr_dir
            directory = os.path.join(self.destdir, copr_dir)
            self.log.info("RemoveDirs: removing %s", directory)
            try:
                shutil.rmtree(directory)
            except FileNotFoundError:
                self.log.error("RemoveDirs: %s not found", directory)

    def run(self):
        result = BackendResultEnum("failure")
        try:
            self._run_internal()
            result = BackendResultEnum("success")
        except OSError:
            self.log.exception("RemoveDirs OSError")
        return result


class ActionQueueTask(BackendQueueTask):
    def __init__(self, task):
        self.task = task

    @property
    def id(self):
        return self.task.data["id"]

    @property
    def frontend_priority(self):
        return self.task.data.get("priority", 0)


class ActionWorkerManager(WorkerManager):
    worker_prefix = 'action_worker'

    def start_task(self, worker_id, task):
        command = [
            'copr-backend-process-action',
            '--daemon',
            '--task-id', repr(task),
            '--worker-id', worker_id,
        ]
        # TODO: mark as started on FE, and let user know in UI
        self.start_daemon_on_background(command)

    def finish_task(self, worker_id, task_info):
        task_id = self.get_task_id_from_worker_id(worker_id)

        result = Munch()
        result.id = int(task_id)
        result.result = int(task_info['status'])

        try:
            self.frontend_client.update({"actions": [result]})
        except FrontendClientException:
            self.log.exception("can't post to frontend, retrying indefinitely")
            return False
        return True
