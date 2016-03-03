import json
import os.path
import shutil
import time
import glob
from urllib import urlretrieve

from munch import Munch
from copr.exceptions import CoprRequestException

from .sign import create_user_keys, CoprKeygenRequestError
from .createrepo import createrepo
from .exceptions import CreateRepoError
from .helpers import get_redis_logger, silent_remove


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
        self.log.info("Action fork {}".format(self.data["object_type"]))
        old_path = os.path.join(self.destdir, self.data["old_value"])
        new_path = os.path.join(self.destdir, self.data["new_value"])
        builds_map = json.loads(self.data["data"])["builds_map"]

        if not os.path.exists(old_path):
            result.result = ActionResult.FAILURE
            return

        for new_id, old_id in builds_map.items():
            # @FIXME Doesnt work for old build because of different folder naming (i.e. msuchy/nanoblogger)
            for build_folder in glob.glob(os.path.join(old_path, "*", str(old_id).zfill(8) + "-*")):

                new_chroot_folder = os.path.dirname(build_folder.replace(old_path, new_path))
                new_build_folder = os.path.join(
                    new_chroot_folder, str(new_id).zfill(8) + os.path.basename(build_folder)[8:])

                if not os.path.exists(new_chroot_folder):
                    os.makedirs(new_chroot_folder)
                shutil.copytree(build_folder, new_build_folder)

                self.log.info("Forking build {} as {}".format(build_folder, new_build_folder))

        result.result = ActionResult.SUCCESS
        result.job_ended_on = time.time()

    def handle_delete_copr_project(self):
        self.log.debug("Action delete copr")
        project = self.data["old_value"]
        path = os.path.normpath(self.destdir + '/' + project)
        if os.path.exists(path):
            self.log.info("Removing copr {0}".format(path))
            shutil.rmtree(path)

    def handle_comps_update(self, result):
        self.log.debug("Action delete build")

        ext_data = json.loads(self.data["data"])
        username = ext_data["username"]
        projectname = ext_data["projectname"]
        chroot = ext_data["chroot"]

        path = self.get_chroot_result_dir(chroot, projectname, username)
        local_comps_path = os.path.join(path, "comps.xml")
        if not ext_data.get("comps_present", True):
            silent_remove(local_comps_path)
        else:
            remote_comps_url = "{}/coprs/{}/{}/chroot/{}/comps/".format(
                self.opts.frontend_base_url,
                username,
                projectname,
                chroot
            )
            try:

                urlretrieve(remote_comps_url, local_comps_path)
                self.log.info("updated comps.xml for {}/{}/{} from {} "
                              .format(username, projectname, chroot, remote_comps_url))
            except Exception:
                self.log.exception("Failed to update comps from {} at location {}"
                                   .format(remote_comps_url, local_comps_path))

        result.result = ActionResult.SUCCESS

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

        if self.opts.do_sign is False:
            # skip key creation, most probably sign component is unused
            result.result = ActionResult.SUCCESS
            return

        try:
            create_user_keys(username, projectname, self.opts)
            result.result = ActionResult.SUCCESS
        except CoprKeygenRequestError:
            result.result = ActionResult.FAILURE

    def handle_rawhide_to_release(self, result):
        data = json.loads(self.data["data"])
        try:
            chrootdir = os.path.join(self.opts.destdir, data["user"], data["copr"], data["dest_chroot"])
            if not os.path.exists(chrootdir):
                self.log.debug("Create directory: {}".format(chrootdir))
                os.makedirs(chrootdir)
                createrepo(path=chrootdir, front_url=self.front_url,
                           username=data["user"], projectname=data["copr"],
                           override_acr_flag=True)

            for build in data["builds"]:
                srcdir = os.path.join(self.opts.destdir, data["user"], data["copr"], data["rawhide_chroot"], build)
                if os.path.exists(srcdir):
                    destdir = os.path.join(chrootdir, build)
                    self.log.debug("Copy directory: {} as {}".format(srcdir, destdir))
                    shutil.copytree(srcdir, destdir)

                    with open(os.path.join(destdir, "build.info"), "a") as f:
                        f.write("\nfrom_chroot={}".format(data["rawhide_chroot"]))
        except:
            result.result = ActionResult.FAILURE

        result.result = ActionResult.SUCCESS

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

        self.log.info("Action result: {}".format(result))

        if "result" in result:
            if result.result == ActionResult.SUCCESS and \
                    not getattr(result, "job_ended_on", None):
                result.job_ended_on = time.time()

            self.frontend_client.update({"actions": [result]})


class ActionType(object):
    DELETE = 0
    RENAME = 1
    LEGAL_FLAG = 2
    CREATEREPO = 3
    UPDATE_COMPS = 4
    GEN_GPG_KEY = 5
    RAWHIDE_TO_RELEASE = 6
    FORK = 7


class ActionResult(object):
    WAITING = 0
    SUCCESS = 1
    FAILURE = 2
