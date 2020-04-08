import copy
import os

from copr_backend.helpers import build_target_dir, build_chroot_log_name


class BuildJob(object):
    def __init__(self, task_data, worker_opts):
        """
            Creates build job object
            :param dict task_dict: dictionary with the following fields
                (based frontend.models.Build)::

                - pkgs: list of space separated urls of packages to build
                - timeout: maximum allowed time of build, build will fail if exceeded # unused
                - project_owner:
                - project_name:
                - project_dirname:
                - submitter:

            :param dict worker_opts: worker options, fields::

                - destdir: worker root directory to store results
                - results_baseurl: root url to stored results
                - timeout: default worker timeout

        """

        self.timeout = worker_opts.timeout
        self.memory_reqs = None
        self.enable_net = True

        self.project_owner = None
        self.project_name = None
        self.project_dirname = None
        self.submitter = None

        self.ended_on = None
        self.started_on = None
        self.submitted_on = None

        self.status = None
        self.chroot = None
        self.arch = None # parsed from chroot

        self.buildroot_pkgs = None

        self.task_id = None
        self.build_id = None

        self.package_name = None
        self.package_version = None

        self.git_repo = None
        self.git_hash = None
        self.git_branch = None

        self.source_type = None
        self.source_json = None

        self.pkg_main_version = None
        self.pkg_epoch = None
        self.pkg_release = None

        self.srpm_url = None
        self.uses_devel_repo = None

        # TODO: validate update data, user marshmallow
        for key, val in task_data.items():
            key = str(key)
            setattr(self, key, val)

        if self.chroot:
            self.arch = self.chroot.rsplit("-", 2)[2]

        if str(self.task_id) == str(self.build_id):
            self.chroot = 'srpm-builds'

        self.destdir = os.path.normpath(os.path.join(
            worker_opts.destdir,
            task_data["project_owner"],
            task_data["project_dirname"]
        ))

        self.results_repo_url = os.path.join(
            worker_opts.results_baseurl,
            task_data["project_owner"],
            task_data["project_dirname"],
        )

        self.result_dir = self.target_dir_name

        self.built_packages = ""

    @property
    def results_dir_url(self):
        return os.path.join(self.results_repo_url, self.chroot, self.target_dir_name)

    @property
    def chroot_dir(self):
        return os.path.normpath("{}/{}".format(self.destdir, self.chroot))

    @property
    def results_dir(self):
        return os.path.join(self.chroot_dir, self.target_dir_name)

    @property
    def target_dir_name(self):
        return build_target_dir(self.build_id, self.package_name)

    @property
    def chroot_log_name(self):
        return build_chroot_log_name(self.build_id, self.package_name)

    @property
    def chroot_log_path(self):
        return os.path.join(self.results_dir, self.chroot_log_name)

    @property
    def rsync_log_name(self):
        return "build-{:08d}.rsync.log".format(self.build_id)

    def update(self, data_dict):
        """

        :param dict data_dict:
        """
        # TODO: validate update data
        self.__dict__.update(data_dict)

    def to_dict(self):
        """

        :return dict: dictified build job
        """
        result = copy.deepcopy(self.__dict__)
        result["id"] = self.build_id
        result["mockchain_macros"] = self.mockchain_macros
        return result

    @property
    def mockchain_macros(self):
        return {
            "copr_username": self.project_owner,
            "copr_projectname": self.project_name,
            "vendor": "Fedora Project COPR ({0}/{1})".format(
                self.project_owner, self.project_name)
        }

    @property
    def pkg_version(self):
        """
        Canonical version presentation release and epoch
        "{epoch}:{version}-{release}"
        """
        if self.pkg_main_version is None:
            return None
        if self.pkg_epoch:
            full_version = "{}:{}".format(self.pkg_epoch, self.pkg_main_version)
        else:
            full_version = "{}".format(self.pkg_main_version)

        if self.pkg_release:
            full_version += "-{}".format(self.pkg_release)
        return full_version

    def __str__(self):
        return str(self.__unicode__())

    def __unicode__(self):
        return u"BuildJob<id: {build_id}, owner: {project_owner}, project: {project_name}, project_dir: {project_dirname}" \
               u"git branch: {git_branch}, git hash: {git_hash}, status: {status} >".format(**self.__dict__)
