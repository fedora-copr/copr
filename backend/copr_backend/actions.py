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
from copr_common.enums import ActionResult
from copr_common.worker_manager import WorkerManager

from copr_backend.worker_manager import BackendQueueTask

from .sign import create_user_keys, CoprKeygenRequestError
from .exceptions import CreateRepoError, CoprSignError, FrontendClientException
from .helpers import (get_redis_logger, silent_remove, ensure_dir_exists,
                      get_chroot_arch, format_filename,
                      uses_devel_repo, call_copr_repo, build_chroot_log_name)
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
            ActionType.LEGAL_FLAG: LegalFlag,
            ActionType.CREATEREPO: Createrepo,
            ActionType.UPDATE_COMPS: CompsUpdate,
            ActionType.GEN_GPG_KEY: GenerateGpgKey,
            ActionType.RAWHIDE_TO_RELEASE: RawhideToRelease,
            ActionType.FORK: Fork,
            ActionType.BUILD_MODULE: BuildModule,
            ActionType.DELETE: Delete,
            ActionType.REMOVE_DIRS: RemoveDirs,
        }.get(action_type, None)

        if action_type == ActionType.DELETE:
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

        self.destdir = self.opts.destdir
        self.front_url = self.opts.frontend_base_url
        self.results_root_url = self.opts.results_baseurl

        self.log = log if log else get_redis_logger(self.opts, "backend.actions", "actions")

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
        data = json.loads(self.data["data"])
        ownername = data["ownername"]
        projectname = data["projectname"]
        project_dirnames = data["project_dirnames"]
        chroots = data["chroots"]
        appstream = data["appstream"]
        devel = data["devel"]

        result = ActionResult.SUCCESS

        done_count = 0
        for project_dirname in project_dirnames:
            for chroot in chroots:
                self.log.info("Creating repo for: {}/{}/{}"
                              .format(ownername, project_dirname, chroot))
                repo = os.path.join(self.destdir, ownername,
                                    project_dirname, chroot)
                try:
                    os.makedirs(repo)
                    self.log.info("Empty repo so far, directory created")
                except FileExistsError:
                    pass

                if not call_copr_repo(repo, appstream=appstream, devel=devel,
                                      logger=self.log):
                    result = ActionResult.FAILURE

        return result


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
            result = ActionResult.FAILURE
            return result

        try:
            pubkey_path = os.path.join(new_path, "pubkey.gpg")
            if not os.path.exists(new_path):
                os.makedirs(new_path)

            if sign:
                # Generate brand new gpg key.
                self.generate_gpg_key(data["user"], data["copr"])
                # Put the new public key into forked build directory.
                get_pubkey(data["user"], data["copr"], self.log, pubkey_path)

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

                    if not os.path.exists(dst_path):
                        os.makedirs(dst_path)

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

            result = ActionResult.SUCCESS
            for chroot_path in chroot_paths:
                if not call_copr_repo(chroot_path, logger=self.log):
                    result = ActionResult.FAILURE

        except (CoprSignError, CreateRepoError, CoprRequestException, IOError) as ex:
            self.log.error("Failure during project forking")
            self.log.error(str(ex))
            self.log.error(traceback.format_exc())
            result = ActionResult.FAILURE
        return result


class Delete(Action):
    """
    Abstract class for all other Delete* classes.
    """
    # pylint: disable=abstract-method
    def _handle_delete_builds(self, ownername, projectname, project_dirname,
                              chroot_builddirs, build_ids, appstream):
        """ call /bin/copr-repo --delete """
        devel = uses_devel_repo(self.front_url, ownername, projectname)
        result = ActionResult.SUCCESS
        for chroot, subdirs in chroot_builddirs.items():
            chroot_path = os.path.join(self.destdir, ownername, project_dirname,
                                       chroot)
            if not os.path.exists(chroot_path):
                self.log.error("%s chroot path doesn't exist", chroot_path)
                result = ActionResult.FAILURE
                continue

            self.log.info("Deleting subdirs [%s] in %s",
                          ", ".join(subdirs), chroot_path)

            # Run createrepo first and then remove the files (to avoid old
            # repodata temporarily pointing at non-existing files)!
            if chroot != "srpm-builds":
                # In srpm-builds we don't create repodata at all
                if not call_copr_repo(chroot_path, delete=subdirs, devel=devel, appstream=appstream,
                                      logger=self.log):
                    result = ActionResult.FAILURE

            for build_id in build_ids or []:
                log_paths = [
                    os.path.join(chroot_path, build_chroot_log_name(build_id)),
                    # we used to create those before
                    os.path.join(chroot_path, 'build-{}.rsync.log'.format(build_id)),
                    os.path.join(chroot_path, 'build-{}.log'.format(build_id))]
                for log_path in log_paths:
                    try:
                        os.unlink(log_path)
                    except OSError:
                        self.log.debug("can't remove %s", log_path)
        return result


class DeleteProject(Delete):
    def run(self):
        self.log.debug("Action delete copr")
        result = ActionResult.SUCCESS

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        project_dirnames = ext_data["project_dirnames"]

        if not ownername:
            self.log.error("Received empty ownername!")
            result = ActionResult.FAILURE
            return result

        for dirname in project_dirnames:
            if not dirname:
                self.log.warning("Received empty dirname!")
                continue
            path = os.path.join(self.destdir, ownername, dirname)
            if os.path.exists(path):
                self.log.info("Removing copr dir {}".format(path))
                shutil.rmtree(path)
        return result


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
        result = ActionResult.SUCCESS
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
                result = ActionResult.FAILURE
        return result


class DeleteMultipleBuilds(Delete):
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
        ext_data = json.loads(self.data["data"])

        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        project_dirnames = ext_data["project_dirnames"]
        build_ids = ext_data["build_ids"]
        appstream = ext_data["appstream"]

        result = ActionResult.SUCCESS
        for project_dirname, chroot_builddirs in project_dirnames.items():
            if ActionResult.FAILURE == \
               self._handle_delete_builds(ownername, projectname,
                                          project_dirname, chroot_builddirs,
                                          build_ids, appstream):
                result = ActionResult.FAILURE
        return result


class DeleteBuild(Delete):
    def run(self):
        self.log.info("Action delete build.")

        # == EXAMPLE DATA ==
        # ownername: @copr
        # projectname: TEST1576047114845905086Project10Fork
        # project_dirname: TEST1576047114845905086Project10Fork:pr:12
        # chroot_builddirs:
        #   srpm-builds: [00849545]
        #   fedora-30-x86_64: [00849545-example]
        ext_data = json.loads(self.data["data"])

        try:
            ownername = ext_data["ownername"]
            build_ids = [self.data['object_id']]
            projectname = ext_data["projectname"]
            project_dirname = ext_data["project_dirname"]
            chroot_builddirs = ext_data["chroot_builddirs"]
            appstream = ext_data["appstream"]
        except KeyError:
            self.log.exception("Invalid action data")
            return ActionResult.FAILURE

        return self._handle_delete_builds(ownername, projectname,
                                          project_dirname, chroot_builddirs,
                                          build_ids, appstream)


class DeleteChroot(Delete):
    def run(self):
        self.log.info("Action delete project chroot.")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        chrootname = ext_data["chrootname"]

        chroot_path = os.path.join(self.destdir, ownername, projectname, chrootname)
        self.log.info("Going to delete: %s", chroot_path)

        if not os.path.isdir(chroot_path):
            self.log.error("Directory %s not found", chroot_path)
            return ActionResult.SUCCESS
        shutil.rmtree(chroot_path)
        return ActionResult.SUCCESS


class GenerateGpgKey(Action, GPGMixin):
    def run(self):
        ext_data = json.loads(self.data["data"])
        self.log.info("Action generate gpg key: %s", ext_data)

        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]

        success = self.generate_gpg_key(ownername, projectname)
        return ActionResult.SUCCESS if success else ActionResult.FAILURE


class RawhideToRelease(Action):
    def run(self):
        data = json.loads(self.data["data"])
        appstream = data["appstream"]
        result = ActionResult.SUCCESS
        try:
            chrootdir = os.path.join(self.opts.destdir, data["ownername"], data["projectname"], data["dest_chroot"])
            if not os.path.exists(chrootdir):
                self.log.info("Create directory: %s", chrootdir)
                os.makedirs(chrootdir)

            for build in data["builds"]:
                srcdir = os.path.join(self.opts.destdir, data["ownername"],
                                      data["projectname"], data["rawhide_chroot"], build)
                if os.path.exists(srcdir):
                    destdir = os.path.join(chrootdir, build)
                    self.log.info("Copy directory: %s as %s", srcdir, destdir)
                    shutil.copytree(srcdir, destdir)

                    with open(os.path.join(destdir, "build.info"), "a") as f:
                        f.write("\nfrom_chroot={}".format(data["rawhide_chroot"]))

            if not call_copr_repo(chrootdir, appstream=appstream, logger=self.log):
                result = ActionResult.FAILURE
        except:
            result = ActionResult.FAILURE

        return result


class BuildModule(Action):
    def run(self):
        result = ActionResult.SUCCESS
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
                    dirs = [d for d in os.listdir(srcdir) if d.startswith(tuple(prefixes))]
                    for folder in dirs:
                        shutil.copytree(os.path.join(srcdir, folder), os.path.join(destdir, folder))
                        self.log.info("Copy directory: %s as %s",
                                      os.path.join(srcdir, folder), os.path.join(destdir, folder))

                        for f in os.listdir(os.path.join(destdir, folder)):
                            if not f.endswith(".rpm") or f.endswith(".src.rpm"):
                                continue
                            artifact = format_filename(zero_epoch=True, *splitFilename(f))
                            artifacts.add(artifact)

                    mmd_yaml = modulemd_tools.yaml.update(mmd_yaml, rpms_nevras=artifacts)
                    self.log.info("Module artifacts: %s", artifacts)
                    modulemd_tools.yaml.dump(mmd_yaml, destdir)
                    if not call_copr_repo(destdir, appstream=appstream, logger=self.log):
                        result = ActionResult.FAILURE

        except Exception:
            self.log.exception("handle_build_module failed")
            result = ActionResult.FAILURE

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
        result = ActionResult.FAILURE
        try:
            self._run_internal()
            result = ActionResult.SUCCESS
        except OSError:
            self.log.exception("RemoveDirs OSError")
        return result


# TODO: sync with ActionTypeEnum from common
class ActionType(object):
    DELETE = 0
    RENAME = 1
    LEGAL_FLAG = 2
    CREATEREPO = 3
    UPDATE_COMPS = 4
    GEN_GPG_KEY = 5
    RAWHIDE_TO_RELEASE = 6
    FORK = 7
    UPDATE_MODULE_MD = 8  # Deprecated
    BUILD_MODULE = 9
    CANCEL_BUILD = 10
    REMOVE_DIRS = 11


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
