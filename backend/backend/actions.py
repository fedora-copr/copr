import json
import os.path
import shutil
import time

from bunch import Bunch

from .createrepo import createrepo, createrepo_unsafe
from exceptions import CreateRepoError
from .helpers import get_redis_logger


class Action(object):
    """ Object to send data back to fronted

    :param multiprocessing.Lock lock: Global lock for backend
    :param backend.callback.FrontendCallback frontent_callback:
        object to post data back to frontend

    :param destdir: filepath with build results

    :param dict action: dict-like object with action task

    Expected **action** keys:

        - action_type: main field determining what action to apply
        # TODO: describe actions

    """
    # TODO: get more form opts, decrease number of parameters
    def __init__(self, opts, action, lock, frontend_client):

        self.opts = opts
        self.frontend_client = frontend_client
        self.data = action

        self.lock = lock

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

            path = os.path.join(self.destdir, username, projectname, chroot)

            try:
                createrepo(path=path, front_url=self.front_url,
                           username=username, projectname=projectname,
                           override_acr_flag=True,
                           lock=self.lock)
                done_count += 1
            except CreateRepoError:
                self.log.exception("Error making local repo for: {}/{}/{}"
                                   .format(username, projectname, chroot))

        if done_count == len(chroots):
            result.result = ActionResult.SUCCESS
        else:
            result.result = ActionResult.FAILURE

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

    def handle_delete_copr_project(self):
        self.log.debug("Action delete copr")
        project = self.data["old_value"]
        path = os.path.normpath(self.destdir + '/' + project)
        if os.path.exists(path):
            self.log.info("Removing copr {0}".format(path))
            shutil.rmtree(path)

    def handle_delete_build(self):
        self.log.debug("Action delete build")
        project = self.data["old_value"]

        ext_data = json.loads(self.data["data"])
        username = ext_data["username"]
        projectname = ext_data["projectname"]
        chroots_requested = set(ext_data["chroots"])

        if not ext_data.get("src_pkg_name"):
            self.log.error("Delete build action missing `src_pkg_name` field, check frontend version. Raw ext_data: {}"
                           .format(ext_data))
            return

        package_name = ext_data["src_pkg_name"]
        path = os.path.join(self.destdir, project)

        self.log.info("Deleting package {0}".format(package_name))
        self.log.info("Copr path {0}".format(path))

        try:
            chroot_list = set(os.listdir(path))
        except OSError:
            # already deleted
            chroot_list = set()

        chroots_to_do = chroot_list.intersection(chroots_requested)
        if not chroots_to_do:
            self.log.info("Nothing to delete for delete action: package {}, {}"
                          .format(package_name, ext_data))
            return

        for chroot in chroots_to_do:
            self.log.debug("In chroot {0}".format(chroot))
            altered = False

            pkg_path = os.path.join(path, chroot, package_name)
            if os.path.isdir(pkg_path):
                self.log.info("Removing build {0}".format(pkg_path))
                shutil.rmtree(pkg_path)
                altered = True
            else:
                self.log.debug("Package {0} dir not found in chroot {1}".format(package_name, chroot))

            if altered:
                self.log.debug("Running createrepo")

                result_base_url = "/".join(
                    [self.results_root_url, username, projectname, chroot])
                createrepo_target = os.path.join(path, chroot)
                try:
                    createrepo(
                        path=createrepo_target, lock=self.lock,
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

    def run(self):
        """ Handle action (other then builds) - like rename or delete of project """
        result = Bunch()
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

        elif action_type == ActionType.CREATEREPO:
            self.handle_createrepo(result)

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


class ActionResult(object):
    WAITING = 0
    SUCCESS = 1
    FAILURE = 2
