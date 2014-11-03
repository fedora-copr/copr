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

        self.project_owner = None
        self.project_name = None
        self.submitter = None

        self.ended_on = None
        self.started_on = None
        self.submitted_on = None

        self.status = None
        self.chroot = None

        # TODO: validate update data
        for key, val in task_data.items():
            key = str(key)
            setattr(self, key, val)

        #self.__dict__.update(task_data)

        self.pkgs = [task_data["pkgs"]]  # just for now
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

        self.pkg_version = ""
        self.built_packages = ""

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

        return result

    def __unicode__(self):
        return u"BuildJob<id: {build_id}, owner: {project_owner}, " \
               u"project: {project_name},>".format(self.__dict__)
