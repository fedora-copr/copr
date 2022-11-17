"""
ImportDispatcher related classes.
"""

import os
import sys
import logging
from copr_common.dispatcher import Dispatcher
from copr_common.worker_manager import GroupWorkerLimit
from copr_dist_git.importer import Importer, ImportWorkerManager


# TODO Move this to the config file
LIMITS = {
    "sandbox": 3,
    "owner": 5,
}


class _PriorityCounter:
    def __init__(self):
        self._counter = {}

    def get_priority(self, task):
        """
        Calculate the "dynamic" import task priority.
        _counter["sandbox"] = value
        """
        self._counter.setdefault(task.sandbox, 0)
        self._counter[task.sandbox] += 1
        return self._counter[task.sandbox]


class ImportDispatcher(Dispatcher):
    """
    Kick-off a dispatcher daemon for importing tasks into DistGit.
    """
    task_type = 'import'
    worker_manager_class = ImportWorkerManager

    def __init__(self, opts):
        super().__init__(opts)

        self.log = self._get_logger()
        self.sleeptime = opts.sleep_time
        self.max_workers = self.opts.max_workers

        for limit_type in ['sandbox', 'owner']:
            limit = LIMITS[limit_type]
            self.log.info("setting %s limit to %s", limit_type, limit)
            self.limits.append(GroupWorkerLimit(
                lambda x, limit=limit_type: getattr(x, limit),
                limit,
                name=limit_type,
            ))

        self._create_per_task_logs_directory(self.opts.per_task_log_dir)

    def get_frontend_tasks(self):
        importer = Importer(self.opts)
        tasks = importer.try_to_obtain_new_tasks(limit=999999)
        counter = _PriorityCounter()
        for task in tasks:
            task.dispatcher_priority += counter.get_priority(task)
        return tasks

    def _create_per_task_logs_directory(self, path):
        self.log.info("Make sure per-task-logs dir exists at: %s", path)
        try:
            os.makedirs(path)
        except OSError:
            if not os.path.isdir(path):
                self.log.error(
                    "Could not create per-task-logs directory at path %s", path)
                sys.exit(1)

    def _get_logger(self):
        formatstr = ("[%(asctime)s][%(levelname)s][%(name)s]"
                     "[%(module)s:%(lineno)d][pid:%(process)d] %(message)s")
        logging.basicConfig(
            filename=os.path.join(self.opts.log_dir, "main.log"),
            level=logging.DEBUG,
            format=formatstr,
            datefmt='%H:%M:%S'
        )
        logging.getLogger('requests.packages.urllib3').setLevel(logging.WARN)
        logging.getLogger('urllib3').setLevel(logging.WARN)
        return logging.getLogger(__name__)
