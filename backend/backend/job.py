import copy
import os


class BuildJob(object):

    def __init__(self, task_data, worker_opts):
        """
            Creates build job object
            :param dict task_dict: dictionary with the following fields
                (based frontend.models.Build)::

                - pkgs: list of space separated urls of packages to build
                - repos: list of space separated additional repos
                - timeout: maximum allowed time of build, build will fail if exceeded # unused
                - project_owner:
                - project_name:
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
        self.submitter = None

        self.ended_on = None
        self.started_on = None
        self.submitted_on = None

        self.status = None
        self.chroot = None

        self.buildroot_pkgs = None

        self.task_id = None

        # TODO: validate update data
        for key, val in task_data.items():
            key = str(key)
            setattr(self, key, val)

        self.pkg = task_data["pkgs"]
        del self.pkgs  # better to produce error, than use it blindly

        self.repos = [r for r in task_data["repos"].split(" ") if r.strip()]
        self.build_id = task_data["build_id"]

        self.destdir = os.path.normpath(os.path.join(
            worker_opts.destdir,
            task_data["project_owner"],
            task_data["project_name"]
        ))

        self.results = u"/".join([
            worker_opts.results_baseurl,
            task_data["project_owner"],
            task_data["project_name"] + "/"
        ])

        self.pkg_main_version = ""
        self.pkg_epoch = None
        self.pkg_release = None

        self.built_packages = ""

    @property
    def pkg_name(self):
        mb_name = self.pkg.split("/")[-1]
        if mb_name:
            mb_name = mb_name.replace(".src.rpm", "")
            return mb_name
        else:
            return self.pkg

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
        result["pkg_version"] = self.pkg_version
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
        return u"BuildJob<id: {build_id}, owner: {project_owner}, " \
               u"project: {project_name}, source pkg : {pkg} >".format(**self.__dict__)
