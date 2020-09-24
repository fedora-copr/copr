# coding: utf-8

from .exceptions import PackageImportException

class ImportTask(object):
    def __init__(self):
        self.build_id = None
        self.owner = None
        self.project = None
        self.branches = []
        self.srpm_url = None

    @staticmethod
    def from_dict(task_dict):
        task = ImportTask()

        try:
            task.build_id = task_dict["build_id"]
            task.owner = task_dict["owner"]
            task.project = task_dict["project"]
            task.branches = task_dict["branches"]
            task.srpm_url = task_dict["srpm_url"]
            task.pkg_name = task_dict["pkg_name"]
        except (KeyError, ValueError) as e:
            raise PackageImportException(str(e))

        return task

    @property
    def repo_namespace(self):
        return "{}/{}".format(self.owner, self.project)

    @property
    def reponame(self):
        return "{}/{}".format(self.repo_namespace, self.pkg_name)

    def __str__(self):
        return "{}({}, #{})".format(self.__class__.__name__,
                                    self.reponame,
                                    self.build_id)
