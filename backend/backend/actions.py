import json
import os
import os.path
import shutil
import time
import glob
import traceback
import base64
import modulemd
import tempfile

from munch import Munch
from distutils.dir_util import copy_tree
from copr.exceptions import CoprRequestException
from requests import RequestException
from urllib.request import urlretrieve

from .sign import create_user_keys, CoprKeygenRequestError
from .createrepo import createrepo
from .exceptions import CreateRepoError, CoprSignError
from .helpers import get_redis_logger, silent_remove, ensure_dir_exists, get_chroot_arch, cmd_debug
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

    def handle_legal_flag(self):
        self.log.debug("Action legal-flag: ignoring")

    def handle_createrepo(self, result):
        self.log.debug("Action create repo")
        data = json.loads(self.data["data"])
        username = data["username"]
        projectname = data["projectname"]
        chroots = data["chroots"]

        done_count = 0
        for chroot in chroots:
            self.log.info("Creating repo for: {}/{}/{}"
                          .format(username, projectname, chroot))

            path = self.get_chroot_result_dir(chroot, projectname, username)

            try:
                createrepo(path=path, front_url=self.front_url,
                           username=username, projectname=projectname,
                           override_acr_flag=True)
                done_count += 1
            except CoprRequestException as err:
                # fixme: dirty hack to catch case when createrepo invoked upon deleted project
                if "does not exists" in str(err):
                    result.result = ActionResult.FAILURE
                    return

            except CreateRepoError:
                self.log.exception("Error making local repo for: {}/{}/{}"
                                   .format(username, projectname, chroot))

        if done_count == len(chroots):
            result.result = ActionResult.SUCCESS
        else:
            result.result = ActionResult.FAILURE

    def get_chroot_result_dir(self, chroot, projectname, username):
        return os.path.join(self.destdir, username, projectname, chroot)

    def handle_rename(self, result):
        self.log.debug("Action rename")
        old_path = os.path.normpath(os.path.join(
            self.destdir, self.data["old_value"]))
        new_path = os.path.normpath(os.path.join(
            self.destdir, self.data["new_value"]))

        if os.path.exists(old_path):
            if not os.path.exists(new_path):
                shutil.move(old_path, new_path)
                result.result = ActionResult.SUCCESS
            else:
                result.message = "Destination directory already exist."
                result.result = ActionResult.FAILURE
        else:  # nothing to do, that is success too
            result.result = ActionResult.SUCCESS
        result.job_ended_on = time.time()

    def handle_fork(self, result):
        sign = self.opts.do_sign
        self.log.info("Action fork {}".format(self.data["object_type"]))
        data = json.loads(self.data["data"])
        old_path = os.path.join(self.destdir, self.data["old_value"])
        new_path = os.path.join(self.destdir, self.data["new_value"])
        builds_map = json.loads(self.data["data"])["builds_map"]

        if not os.path.exists(old_path):
            self.log.info("Source copr directory doesnt exist: {}".format(old_path))
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

            chroots = set()
            for new_id, old_dir_name in builds_map.items():
                for build_folder in glob.glob(os.path.join(old_path, "*", old_dir_name)):
                    new_chroot_folder = os.path.dirname(build_folder.replace(old_path, new_path))
                    chroots.add(new_chroot_folder)

                    # We can remove this ugly condition after migrating Copr to new machines
                    # It is throw-back from era before dist-git
                    new_basename = old_dir_name if not os.path.basename(build_folder)[:8].isdigit() \
                        else str(new_id).zfill(8) + os.path.basename(build_folder)[8:]
                    new_build_folder = os.path.join(new_chroot_folder, new_basename)

                    if not os.path.exists(new_build_folder):
                        os.makedirs(new_build_folder)

                    copy_tree(build_folder, new_build_folder)
                    # Drop old signatures coming from original repo and re-sign.
                    unsign_rpms_in_dir(new_build_folder, opts=self.opts, log=self.log)
                    if sign:
                        sign_rpms_in_dir(data["user"], data["copr"], new_build_folder, opts=self.opts, log=self.log)

                    self.log.info("Forking build {} as {}".format(build_folder, new_build_folder))

            for chroot in chroots:
                createrepo(path=chroot, front_url=self.front_url,
                           username=data["user"], projectname=data["copr"],
                           override_acr_flag=True)

            result.result = ActionResult.SUCCESS
            result.ended_on = time.time()

        except (CoprSignError, CreateRepoError, CoprRequestException, IOError) as ex:
            self.log.error("Failure during project forking")
            self.log.error(str(ex))
            self.log.error(traceback.format_exc())
            result.result = ActionResult.FAILURE

    def handle_delete_copr_project(self):
        self.log.debug("Action delete copr")
        project = self.data["old_value"]
        path = os.path.normpath(self.destdir + '/' + project)
        if os.path.exists(path):
            self.log.info("Removing copr {0}".format(path))
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
            self.log.info("deleted comps.xml for {}/{}/{} from {} "
                          .format(ownername, projectname, chroot, remote_comps_url))
        else:
            try:
                urlretrieve(remote_comps_url, local_comps_path)
                self.log.info("saved comps.xml for {}/{}/{} from {} "
                              .format(ownername, projectname, chroot, remote_comps_url))
            except Exception:
                self.log.exception("Failed to update comps from {} at location {}"
                                   .format(remote_comps_url, local_comps_path))
                result.result = ActionResult.FAILURE

    def handle_module_md_update(self, result):
        self.log.debug("Action module_md update")

        ext_data = json.loads(self.data["data"])
        ownername = ext_data["ownername"]
        projectname = ext_data["projectname"]
        chroot = ext_data["chroot"]
        url_path = ext_data["url_path"]

        remote_module_md_url = self.opts.frontend_base_url + url_path

        path = self.get_chroot_result_dir(chroot, projectname, ownername)
        ensure_dir_exists(path, self.log)
        local_module_md_path = os.path.join(path, "module_md.yaml")
        result.result = ActionResult.SUCCESS
        if not ext_data.get("module_md_present", True):
            silent_remove(local_module_md_path)
            self.log.info("deleted module_md.yaml for {}/{}/{} from {} "
                          .format(ownername, projectname, chroot, remote_module_md_url))
        else:
            try:
                urlretrieve(remote_module_md_url, local_module_md_path)
                self.log.info("saved module_md.yaml for {}/{}/{} from {} "
                              .format(ownername, projectname, chroot, remote_module_md_url))
            except Exception:
                self.log.exception("Failed to update module_md from {} at location {}"
                                   .format(remote_module_md_url, local_module_md_path))
                result.result = ActionResult.FAILURE

    def handle_delete_build(self):
        self.log.debug("Action delete build")
        project = self.data["old_value"]

        ext_data = json.loads(self.data["data"])
        username = ext_data["username"]
        projectname = ext_data["projectname"]
        chroots_requested = set(ext_data["chroots"])

        if "src_pkg_name" not in ext_data and "result_dir_name" not in ext_data:
            self.log.error("Delete build action missing `src_pkg_name` or `result_dir_name` field,"
                           " check frontend version. Raw ext_data: {}"
                           .format(ext_data))
            return

        target_dir = ext_data.get("result_dir_name") or ext_data.get("src_pkg_name")
        if target_dir is None or target_dir == "":
            self.log.error("Bad delete request, ignored. Raw ext_data: {}"
                           .format(ext_data))
            return
        path = os.path.join(self.destdir, project)

        self.log.info("Deleting package {0}".format(target_dir))
        self.log.info("Copr path {0}".format(path))

        try:
            chroot_list = set(os.listdir(path))
        except OSError:
            # already deleted
            chroot_list = set()

        chroots_to_do = chroot_list.intersection(chroots_requested)
        if not chroots_to_do:
            self.log.info("Nothing to delete for delete action: package {}, {}"
                          .format(target_dir, ext_data))
            return

        for chroot in chroots_to_do:
            self.log.debug("In chroot {0}".format(chroot))
            altered = False

            pkg_path = os.path.join(path, chroot, target_dir)
            if os.path.isdir(pkg_path):
                self.log.info("Removing build {0}".format(pkg_path))
                shutil.rmtree(pkg_path)
                altered = True
            else:
                self.log.debug("Package {0} dir not found in chroot {1}".format(target_dir, chroot))

            if altered:
                self.log.debug("Running createrepo")

                result_base_url = "/".join(
                    [self.results_root_url, username, projectname, chroot])
                createrepo_target = os.path.join(path, chroot)
                try:
                    createrepo(
                        path=createrepo_target,
                        front_url=self.front_url, base_url=result_base_url,
                        username=username, projectname=projectname
                    )
                except CoprRequestException:
                    # FIXME: dirty hack to catch the case when createrepo invoked upon a deleted project
                    self.log.exception("Project {0}/{1} has been deleted on frontend".format(username, projectname))
                except CreateRepoError:
                    self.log.exception("Error making local repo: {}".format(createrepo_target))

            logs_to_remove = [
                os.path.join(path, chroot, template.format(self.data['object_id']))
                for template in ['build-{}.log', 'build-{}.rsync.log']
            ]
            for log_path in logs_to_remove:
                if os.path.isfile(log_path):
                    self.log.info("Removing log {0}".format(log_path))
                    os.remove(log_path)

    def handle_generate_gpg_key(self, result):
        ext_data = json.loads(self.data["data"])
        self.log.info("Action generate gpg key: {}".format(ext_data))

        username = ext_data["username"]
        projectname = ext_data["projectname"]

        success = self.generate_gpg_key(username, projectname)
        result.result = ActionResult.SUCCESS if success else ActionResult.FAILURE

    def generate_gpg_key(self, owner, projectname):
        if self.opts.do_sign is False:
            # skip key creation, most probably sign component is unused
            return True
        try:
            create_user_keys(owner, projectname, self.opts)
            return True
        except CoprKeygenRequestError as e:
            self.log.exception(e)
            return False

    def handle_rawhide_to_release(self, result):
        data = json.loads(self.data["data"])
        try:
            chrootdir = os.path.join(self.opts.destdir, data["user"], data["copr"], data["dest_chroot"])
            if not os.path.exists(chrootdir):
                self.log.debug("Create directory: {}".format(chrootdir))
                os.makedirs(chrootdir)

            for build in data["builds"]:
                srcdir = os.path.join(self.opts.destdir, data["user"], data["copr"], data["rawhide_chroot"], build)
                if os.path.exists(srcdir):
                    destdir = os.path.join(chrootdir, build)
                    self.log.debug("Copy directory: {} as {}".format(srcdir, destdir))
                    shutil.copytree(srcdir, destdir)

                    with open(os.path.join(destdir, "build.info"), "a") as f:
                        f.write("\nfrom_chroot={}".format(data["rawhide_chroot"]))

            createrepo(path=chrootdir, front_url=self.front_url,
                       username=data["user"], projectname=data["copr"],
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
            self.log.info("Found VM {0} for task {1}".format(vmd.vm_ip, task_id))
        else:
            self.log.error("No VM found for task {0}".format(task_id))
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
            self.log.exception("Error running cmd: {}".format(cmd))
            result.result = ActionResult.FAILURE
            return

        cmd_debug(cmd, rc, out, err, self.log)

        if rc != 0:
            result.result = ActionResult.FAILURE
            return

        try:
            pid = int(out.strip())
        except ValueError:
            self.log.exception("Invalid pid {} received".format(out))
            result.result = ActionResult.FAILURE
            return

        cmd = "kill -9 -{}".format(pid)
        try:
            rc, out, err = conn.run_expensive(cmd)
        except SSHConnectionError:
            self.log.exception("Error running cmd: {}".format(cmd))
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
            modulemd_data = base64.b64decode(data["modulemd_b64"])
            project_path = os.path.join(self.opts.destdir, ownername, projectname)
            self.log.info(modulemd_data)

            mmd = modulemd.ModuleMetadata()
            mmd.loads(modulemd_data)

            for chroot in chroots:
                arch = get_chroot_arch(chroot)
                srcdir = os.path.join(project_path, chroot)
                module_tag = chroot + '+' + mmd.name + '-' + (mmd.stream or '') + '-' + (str(mmd.version) or '1')
                module_relpath = os.path.join(module_tag, "latest", arch)
                destdir = os.path.join(project_path, "modules", module_relpath)

                if os.path.exists(destdir):
                    self.log.warning("Module {0} already exists. Omitting.".format(destdir))
                else:
                    # We want to copy just the particular module builds
                    # into the module destdir, not the whole chroot
                    os.makedirs(destdir)
                    prefixes = ["{:08d}-".format(x) for x in data["builds"]]
                    dirs = [d for d in os.listdir(srcdir) if d.startswith(tuple(prefixes))]
                    for folder in dirs:
                        shutil.copytree(os.path.join(srcdir, folder), os.path.join(destdir, folder))
                        self.log.info("Copy directory: {} as {}".format(
                            os.path.join(srcdir, folder), os.path.join(destdir, folder)))

                        for f in os.listdir(os.path.join(destdir, folder)):
                            if not f.endswith(".rpm") or f.endswith(".src.rpm"):
                                continue
                            mmd.artifacts.rpms.add(str(f.rstrip(".rpm")))

                    self.log.info("Module artifacts: {}".format(mmd.artifacts.rpms))
                    modulemd.dump_all(os.path.join(destdir, "modules.yaml"), [mmd])
                    createrepo(path=destdir, front_url=self.front_url,
                               username=ownername, projectname=projectname,
                               override_acr_flag=True)

            result.result = ActionResult.SUCCESS
        except Exception as e:
            self.log.error(str(e))
            result.result = ActionResult.FAILURE

    def run(self):
        """ Handle action (other then builds) - like rename or delete of project """
        result = Munch()
        result.id = self.data["id"]

        action_type = self.data["action_type"]

        if action_type == ActionType.DELETE:
            if self.data["object_type"] == "copr":
                self.handle_delete_copr_project()
            elif self.data["object_type"] == "build":
                self.handle_delete_build()

            result.result = ActionResult.SUCCESS

        elif action_type == ActionType.LEGAL_FLAG:
            self.handle_legal_flag()

        elif action_type == ActionType.RENAME:
            self.handle_rename(result)

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

        elif action_type == ActionType.UPDATE_MODULE_MD:
            self.handle_module_md_update(result)

        elif action_type == ActionType.BUILD_MODULE:
            self.handle_build_module(result)

        elif action_type == ActionType.CANCEL_BUILD:
            self.handle_cancel_build(result)

        self.log.info("Action result: {}".format(result))

        if "result" in result:
            if result.result == ActionResult.SUCCESS and \
                    not getattr(result, "job_ended_on", None):
                result.job_ended_on = time.time()

            try:
                self.frontend_client.update({"actions": [result]})
            except RequestException as e:
                self.log.exception(e)


class ActionType(object):
    DELETE = 0
    RENAME = 1
    LEGAL_FLAG = 2
    CREATEREPO = 3
    UPDATE_COMPS = 4
    GEN_GPG_KEY = 5
    RAWHIDE_TO_RELEASE = 6
    FORK = 7
    UPDATE_MODULE_MD = 8
    BUILD_MODULE = 9
    CANCEL_BUILD = 10


class ActionResult(object):
    WAITING = 0
    SUCCESS = 1
    FAILURE = 2
