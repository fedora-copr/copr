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

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd

from copr_common.rpm import splitFilename
from .sign import create_user_keys, CoprKeygenRequestError
from .createrepo import createrepo
from .exceptions import CreateRepoError, CoprSignError
from .helpers import get_redis_logger, silent_remove, ensure_dir_exists, get_chroot_arch, cmd_debug, format_filename
from .sign import sign_rpms_in_dir, unsign_rpms_in_dir, get_pubkey

from .vm_manage.manager import VmManager

from .sshcmd import SSHConnectionError, SSHConnection


class Action(object):
    """ Object to send data back to fronted

    :param backend.callback.FrontendCallback frontent_callback:
        object to post data back to frontend

    :param destdir: filepath with build results

    :param dict action: dict-like object with action task

    Expected **action** keys:

        - action_type: main field determining what action to apply
        # TODO: describe actions

    """
    # TODO: get more form opts, decrease number of parameters
    def __init__(self, opts, action, frontend_client):

        self.opts = opts
        self.frontend_client = frontend_client
        self.data = action

        self.destdir = self.opts.destdir
        self.front_url = self.opts.frontend_base_url
        self.results_root_url = self.opts.results_baseurl

        self.log = get_redis_logger(self.opts, "backend.actions", "actions")

    def __str__(self):
        return "<Action: {}>".format(self.data)

    def get_chroot_result_dir(self, chroot, project_dirname, ownername):
        return os.path.join(self.destdir, ownername, project_dirname, chroot)

    def handle_legal_flag(self):
        self.log.debug("Action legal-flag: ignoring")

    def handle_createrepo(self, result):
        self.log.info("Action createrepo")
        data = json.loads(self.data["data"])
        ownername = data["ownername"]
        projectname = data["projectname"]
        project_dirnames = data["project_dirnames"]
        chroots = data["chroots"]

        done_count = 0
        for project_dirname in project_dirnames:
            for chroot in chroots:
                self.log.info("Creating repo for: {}/{}/{}"
                              .format(ownername, project_dirname, chroot))

                path = self.get_chroot_result_dir(chroot, project_dirname, ownername)
                try:
                    os.makedirs(path)
                except FileExistsError:
                    pass

                try:
                    createrepo(path=path, front_url=self.front_url,
                               username=ownername, projectname=projectname,
                               override_acr_flag=True)
                    done_count += 1
                except CoprRequestException as err:
                    # fixme: dirty hack to catch case when createrepo invoked upon deleted project
                    if "does not exists" in str(err):
                        result.result = ActionResult.FAILURE
                        return
                except CreateRepoError:
                    self.log.exception("Error making local repo for: {}/{}/{}"
                                       .format(ownername, project_dirname, chroot))

        if done_count == len(project_dirnames)*len(chroots):
            result.result = ActionResult.SUCCESS
        else:
            result.result = ActionResult.FAILURE

    def handle_fork(self, result):
        sign = self.opts.do_sign
        self.log.info("Action fork %s", self.data["object_type"])
        data = json.loads(self.data["data"])
        old_path = os.path.join(self.destdir, self.data["old_value"])
        new_path = os.path.join(self.destdir, self.data["new_value"])
        builds_map = json.loads(self.data["data"])["builds_map"]

        if not os.path.exists(old_path):
            self.log.info("Source copr directory doesn't exist: %s", old_path)
            result.result = ActionResult.FAILURE
            return

        try:
            pubkey_path = os.path.join(new_path, "pubkey.gpg")
            if not os.path.exists(new_path):
                os.makedirs(new_path)

            if sign:
                # Generate brand new gpg key.
                self.generate_gpg_key(data["user"], data["copr"])
                # Put the new public key into forked build directory.
                get_pubkey(data["user"], data["copr"], pubkey_path)

            chroot_paths = set()
            for chroot, src_dst_dir in builds_map.items():
                src_dir, dst_dir = src_dst_dir[0], src_dst_dir[1]
                if not chroot or not src_dir or not dst_dir:
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
                    sign_rpms_in_dir(data["user"], data["copr"], dst_path, opts=self.opts, log=self.log)

                self.log.info("Forked build %s as %s", src_path, dst_path)

            for chroot_path in chroot_paths:
                createrepo(path=chroot_path, front_url=self.front_url,
                           username=data["user"], projectname=data["copr"],
                           override_acr_flag=True)

            result.result = ActionResult.SUCCESS
            result.ended_on = time.time()

        except (CoprSignError, CreateRepoError, CoprRequestException, IOError) as ex:
            self.log.error("Failure during project forking")
            self.log.error(str(ex))
            self.log.error(traceback.format_exc())
            result.result = ActionResult.FAILURE

    def handle_delete_project(self, result):
        self.log.debug("Action delete copr")
        result.result = ActionResult.SUCCESS

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        project_dirnames = ext_data["project_dirnames"]

        if not ownername:
            self.log.error("Received empty ownername!")
            result.result = ActionResult.FAILURE
            return

        for dirname in project_dirnames:
            if not dirname:
                self.log.warning("Received empty dirname!")
                continue
            path = os.path.join(self.destdir, ownername, dirname)
            if os.path.exists(path):
                self.log.info("Removing copr dir {}".format(path))
                shutil.rmtree(path)

    def handle_comps_update(self, result):
        self.log.debug("Action comps update")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        chroot = ext_data["chroot"]
        url_path = ext_data["url_path"]

        remote_comps_url = self.opts.frontend_base_url + url_path
        self.log.info(remote_comps_url)

        path = self.get_chroot_result_dir(chroot, projectname, ownername)
        ensure_dir_exists(path, self.log)
        local_comps_path = os.path.join(path, "comps.xml")
        result.result = ActionResult.SUCCESS
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
                result.result = ActionResult.FAILURE

    def handle_delete_build(self):
        self.log.info("Action delete build.")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        project_dirname = ext_data["project_dirname"]
        chroot_builddirs = ext_data["chroot_builddirs"]

        self.log.info("Going to delete: %s", chroot_builddirs)

        for chroot, builddir in chroot_builddirs.items():
            if not builddir:
                self.log.warning("Received empty builddir!")
                continue

            chroot_path = os.path.join(self.destdir, ownername, project_dirname, chroot)
            builddir_path = os.path.join(chroot_path, builddir)

            if not os.path.isdir(builddir_path):
                self.log.error("%s not found", builddir_path)
                continue

            self.log.debug("builddir to be deleted %s", builddir_path)
            shutil.rmtree(builddir_path)

            self.log.debug("Running createrepo on %s", chroot_path)
            result_base_url = "/".join(
                [self.results_root_url, ownername, project_dirname, chroot])

            project = "{}/{}".format(ownername, project_dirname)
            if  project in self.opts.build_deleting_without_createrepo.split():
                self.log.warning("createrepo takes too long in %s, skipped",
                                 project)
                return

            try:
                createrepo(
                    path=chroot_path,
                    front_url=self.front_url, base_url=result_base_url,
                    username=ownername, projectname=projectname)
            except CoprRequestException:
                # FIXME: dirty hack to catch the case when createrepo invoked upon a deleted project
                self.log.exception("Project %s/%s has been deleted on frontend", ownername, projectname)
            except CreateRepoError:
                self.log.exception("Error making local repo: %s", full_path)

    def handle_delete_chroot(self):
        self.log.info("Action delete project chroot.")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        chrootname = ext_data["chrootname"]

        chroot_path = os.path.join(self.destdir, ownername, projectname, chrootname)
        self.log.info("Going to delete: %s", chroot_path)

        if not os.path.isdir(chroot_path):
            self.log.error("Directory %s not found", chroot_path)
            return
        shutil.rmtree(chroot_path)

    def handle_generate_gpg_key(self, result):
        ext_data = json.loads(self.data["data"])
        self.log.info("Action generate gpg key: %s", ext_data)

        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]

        success = self.generate_gpg_key(ownername, projectname)
        result.result = ActionResult.SUCCESS if success else ActionResult.FAILURE

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

    def handle_rawhide_to_release(self, result):
        data = json.loads(self.data["data"])
        try:
            chrootdir = os.path.join(self.opts.destdir, data["ownername"], data["projectname"], data["dest_chroot"])
            if not os.path.exists(chrootdir):
                self.log.debug("Create directory: %s", chrootdir)
                os.makedirs(chrootdir)

            for build in data["builds"]:
                srcdir = os.path.join(self.opts.destdir, data["ownername"],
                                      data["projectname"], data["rawhide_chroot"], build)
                if os.path.exists(srcdir):
                    destdir = os.path.join(chrootdir, build)
                    self.log.debug("Copy directory: %s as %s", srcdir, destdir)
                    shutil.copytree(srcdir, destdir)

                    with open(os.path.join(destdir, "build.info"), "a") as f:
                        f.write("\nfrom_chroot={}".format(data["rawhide_chroot"]))

            createrepo(path=chrootdir, front_url=self.front_url,
                       username=data["ownername"], projectname=data["projectname"],
                       override_acr_flag=True)
        except:
            result.result = ActionResult.FAILURE

        result.result = ActionResult.SUCCESS

    def handle_cancel_build(self, result):
        result.result = ActionResult.SUCCESS
        data = json.loads(self.data["data"])
        task_id = data["task_id"]

        vmm = VmManager(self.opts)
        vmd = vmm.get_vm_by_task_id(task_id)
        if vmd:
            self.log.info("Found VM %s for task %s", vmd.vm_ip, task_id)
        else:
            self.log.error("No VM found for task %s", task_id)
            result.result = ActionResult.FAILURE
            return

        conn = SSHConnection(
            user=self.opts.build_user,
            host=vmd.vm_ip,
            config_file=self.opts.ssh.builder_config
        )

        cmd = "cat /var/lib/copr-rpmbuild/pid"
        try:
            rc, out, err = conn.run_expensive(cmd)
        except SSHConnectionError:
            self.log.exception("Error running cmd: %s", cmd)
            result.result = ActionResult.FAILURE
            return

        cmd_debug(cmd, rc, out, err, self.log)

        if rc != 0:
            result.result = ActionResult.FAILURE
            return

        try:
            pid = int(out.strip())
        except ValueError:
            self.log.exception("Invalid pid %s received", out)
            result.result = ActionResult.FAILURE
            return

        cmd = "kill -9 -{}".format(pid)
        try:
            rc, out, err = conn.run_expensive(cmd)
        except SSHConnectionError:
            self.log.exception("Error running cmd: %s", cmd)
            result.result = ActionResult.FAILURE
            return

        cmd_debug(cmd, rc, out, err, self.log)
        result.result = ActionResult.SUCCESS


    def handle_build_module(self, result):
        try:
            data = json.loads(self.data["data"])
            ownername = data["ownername"]
            projectname = data["projectname"]
            chroots = data["chroots"]
            modulemd_data = base64.b64decode(data["modulemd_b64"]).decode("utf-8")
            project_path = os.path.join(self.opts.destdir, ownername, projectname)
            self.log.info(modulemd_data)

            for chroot in chroots:
                arch = get_chroot_arch(chroot)
                mmd = Modulemd.ModuleStream()
                mmd.import_from_string(modulemd_data)
                mmd.set_arch(arch)
                artifacts = Modulemd.SimpleSet()

                srcdir = os.path.join(project_path, chroot)
                module_tag = "{}+{}-{}-{}".format(chroot, mmd.get_name(), (mmd.get_stream() or ''),
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

                    mmd.set_rpm_artifacts(artifacts)
                    self.log.info("Module artifacts: %s", mmd.get_rpm_artifacts())
                    Modulemd.dump([mmd], os.path.join(destdir, "modules.yaml"))
                    createrepo(path=destdir, front_url=self.front_url,
                               username=ownername, projectname=projectname,
                               override_acr_flag=True)

            result.result = ActionResult.SUCCESS
        except Exception as e:
            self.log.error(str(e))
            result.result = ActionResult.FAILURE

    def run(self):
        """ Handle action (other then builds) - like rename or delete of project """
        self.log.info("Executing: %s", str(self))

        result = Munch()
        result.id = self.data["id"]

        action_type = self.data["action_type"]

        if action_type == ActionType.DELETE:
            if self.data["object_type"] == "copr":
                self.handle_delete_project(result)
            elif self.data["object_type"] == "build":
                self.handle_delete_build()
            elif self.data["object_type"] == "chroot":
                self.handle_delete_chroot()

            result.result = ActionResult.SUCCESS

        elif action_type == ActionType.LEGAL_FLAG:
            self.handle_legal_flag()

        elif action_type == ActionType.FORK:
            self.handle_fork(result)

        elif action_type == ActionType.CREATEREPO:
            self.handle_createrepo(result)

        elif action_type == ActionType.UPDATE_COMPS:
            self.handle_comps_update(result)

        elif action_type == ActionType.GEN_GPG_KEY:
            self.handle_generate_gpg_key(result)

        elif action_type == ActionType.RAWHIDE_TO_RELEASE:
            self.handle_rawhide_to_release(result)

        elif action_type == ActionType.BUILD_MODULE:
            self.handle_build_module(result)

        elif action_type == ActionType.CANCEL_BUILD:
            self.handle_cancel_build(result)

        self.log.info("Action result: %s", result)

        if "result" in result:
            if result.result == ActionResult.SUCCESS and \
                    not getattr(result, "job_ended_on", None):
                result.job_ended_on = time.time()

            try:
                self.frontend_client.update({"actions": [result]})
            except RequestException as e:
                self.log.exception(e)


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


class ActionResult(object):
    WAITING = 0
    SUCCESS = 1
    FAILURE = 2
