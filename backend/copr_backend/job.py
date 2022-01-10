import copy
import os

from copr_backend.exceptions import CoprBackendSrpmError
from copr_backend.helpers import build_target_dir


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

        self.pkg_name = None
        self.pkg_main_version = None
        self.pkg_epoch = None
        self.pkg_release = None

        self.srpm_url = None
        self.uses_devel_repo = None
        self.sandbox = None

        self.results = None
        self.appstream = None

        # TODO: validate update data, user marshmallow
        for key, val in task_data.items():
            key = str(key)
            setattr(self, key, val)

        if self.chroot:
            self.arch = self.chroot.rsplit("-", 2)[2]

        if str(self.task_id) == str(self.build_id):
            self.chroot = 'srpm-builds'

        if task_data["appstream"]:
            self.appstream = task_data["appstream"]

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

        # TODO: We should rename this attribute.  This one is used by Frontend
        # to store updated "target_dir_name" to BuildChroot database.  But the
        # name is terrible, and clashes with self.results_dir (plural).
        self.result_dir = self.target_dir_name

        self.built_packages = ""

        self.tags = ["arch_{}".format(self.arch if self.arch else "noarch")]
        if "tags" in task_data:
            self.tags.extend(task_data["tags"])

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
    def backend_log(self):
        """
        The log file which is "live" appended to build resultdir by copr
        backend background process.
        """
        return os.path.join(self.results_dir, "backend.log")

    @property
    def builder_log(self):
        """
        The live log continuously transferred from builder.
        """
        return os.path.join(self.results_dir, "builder-live.log")

    @property
    def rsync_log_name(self):
        return "build-{:08d}.rsync.log".format(self.build_id)

    def update(self, data_dict):
        """

        :param dict data_dict:
        """
        # TODO: validate update data
        self.__dict__.update(data_dict)

    def validate(self):
        """
        Make sure the build results don't contain anything problematic
        """
        if self.pkg_name and len(self.pkg_name) > 100:
            msg = "Too long package name: {0}".format(self.pkg_name)
            # Truncate the package name otherwise frontend won't be able to
            # handle it
            self.pkg_name = None
            raise CoprBackendSrpmError(msg)

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

    @property
    def took_seconds(self):
        """ Number of seconds spent on building this package """
        if self.ended_on is None or self.started_on is None:
            return None
        return self.ended_on - self.started_on
