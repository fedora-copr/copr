# coding: utf-8

import json

from exceptions import PackageImportException

class ImportTask(object):
    def __init__(self):
        self.task_id = None
        self.user = None
        self.project = None
        self.branches = []

        self.source_type = None
        self.source_data = None

    @staticmethod
    def from_dict(task_dict):
        task = ImportTask()

        try:
            task.task_id = task_dict["task_id"]
            task.user = task_dict["user"]
            task.project = task_dict["project"]
            task.branches = task_dict["branches"]
            task.source_data = json.loads(task_dict["source_json"])
        except (KeyError, ValueError) as e:
            raise PackageImportException(str(e))

        return task

    @property
    def repo_namespace(self):
        return "{}/{}".format(self.user, self.project)
