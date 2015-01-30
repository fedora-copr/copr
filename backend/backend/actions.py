import json
import os.path
import shutil
import time

from bunch import Bunch

from .createrepo import createrepo, createrepo_unsafe


class Action(object):
    """ Object to send data back to fronted

    :param multiprocessing.Queue events: collects events for logging
    :param multiprocessing.Lock lock: Global lock for backend
    :param backend.callback.FrontendCallback frontent_callback:
        object to post data back to frontend

    :param destdir: filepath with build results

    :param dict action: dict-like object with action task

    Expected **action** keys:

        - action_type: main field determining what action to apply
        # TODO: describe actions

    """

    def __init__(self, events, action, lock,
                 frontend_callback, destdir,
                 front_url, results_root_url):
        super(Action, self).__init__()
        self.frontend_callback = frontend_callback
        self.destdir = destdir
        self.data = action
        self.events = events
        self.lock = lock
        self.front_url = front_url
        self.results_root_url = results_root_url

    def __str__(self):
        return "<Action: {}>".format(self.data)

    def add_event(self, what):
        self.events.put({"when": time.time(), "who": "action", "what": what})

    def handle_legal_flag(self):
        self.add_event("Action legal-flag: ignoring")

    def handle_createrepo(self, result):
        self.add_event("Action create repo")
        data = json.loads(self.data["data"])
        username = data["username"]
        projectname = data["projectname"]
        chroots = data["chroots"]

        failure = False
        for chroot in chroots:
            self.add_event("Creating repo for: {}/{}/{}".format(username, projectname, chroot))

            path = os.path.join(self.destdir, username, projectname, chroot)

            errcode, _, err = createrepo_unsafe(path=path, lock=self.lock)
            if errcode != 0 or err.strip():
                self.add_event("Error making local repo: {0}".format(err))
                failure = True

        if failure:
            result.result = ActionResult.FAILURE
        else:
            result.result = ActionResult.SUCCESS

    def handle_rename(self, result):
        self.add_event("Action rename")
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
        self.add_event("Action delete copr")
        project = self.data["old_value"]
        path = os.path.normpath(self.destdir + '/' + project)
        if os.path.exists(path):
            self.add_event("Removing copr {0}".format(path))
            shutil.rmtree(path)

    def handle_delete_build(self):
        self.add_event("Action delete build")
        project = self.data["old_value"]

        ext_data = json.loads(self.data["data"])
        username = ext_data["username"]
        projectname = ext_data["projectname"]
        chroots_requested = set(ext_data["chroots"])

        packages = [os.path.basename(x).replace(".src.rpm", "")
                    for x in ext_data["pkgs"].split()]

        path = os.path.join(self.destdir, project)

        self.add_event("Packages to delete {0}".format(' '.join(packages)))
        self.add_event("Copr path {0}".format(path))

        try:
            chroot_list = set(os.listdir(path))
        except OSError:
            # already deleted
            chroot_list = set()

        chroots_to_do = chroot_list.intersection(chroots_requested)
        if not chroots_to_do:
            self.add_event("Nothing to delete for delete action: packages {}, {}"
                           .format(packages, ext_data))
            return

        for chroot in chroots_to_do:
            self.add_event("In chroot {0}".format(chroot))
            altered = False

            for pkg in packages:
                pkg_path = os.path.join(path, chroot, pkg)
                if os.path.isdir(pkg_path):
                    self.add_event("Removing build {0}".format(pkg_path))
                    shutil.rmtree(pkg_path)
                    altered = True
                else:
                    self.add_event(
                        "Package {0} dir not found in chroot {1}"
                        .format(pkg, chroot))

            if altered:
                self.add_event("Running createrepo")

                result_base_url = "/".join(
                    [self.results_root_url, username, projectname, chroot])
                _, _, err = createrepo(
                    path=os.path.join(path, chroot), lock=self.lock,
                    front_url=self.front_url, base_url=result_base_url,
                    username=username, projectname=projectname
                )
                if err.strip():
                    self.add_event(
                        "Error making local repo: {0}".format(err))

            logs_to_remove = [
                os.path.join(path, chroot, template.format(self.data['object_id']))
                for template in ['build-{}.log', 'build-{}.rsync.log']
            ]
            for log_path in logs_to_remove:
                if os.path.isfile(log_path):
                    self.add_event("Removing log {0}".format(log_path))
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

            self.frontend_callback.update({"actions": [result]})


class ActionType(object):
    DELETE = 0
    RENAME = 1
    LEGAL_FLAG = 2
    CREATEREPO = 3


class ActionResult(object):
    WAITING = 0
    SUCCESS = 1
    FAILURE = 2
