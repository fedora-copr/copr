import os
import json
import time
import logging
import tempfile
import shutil

from requests import get, post

from copr_common.worker_manager import WorkerManager

from .package_import import import_package
from .process_pool import Worker, Pool, SingleThreadWorker
from .exceptions import PackageImportException
from .import_task import ImportTask

from . import helpers

log = logging.getLogger(__name__)

class Importer(object):
    def __init__(self, opts):
        self.is_running = False
        self.opts = opts

        self.get_url = "{}/backend/importing/".format(self.opts.frontend_base_url)
        self.post_back_url = "{}/backend/import-completed/".format(self.opts.frontend_base_url)
        self.auth = ("user", self.opts.frontend_auth)
        self.headers = {"content-type": "application/json"}

        self.tmp_root = None

    def try_to_obtain_new_tasks(self, exclude=None, limit=1):
        log.debug("Get task data...")
        if exclude is None:
            exclude = []
        try:
            # get the data
            r = get(self.get_url)
            # take the first task
            builds = list(filter(lambda x: x["build_id"] not in exclude, r.json()))
            if not builds:
                log.debug("No new tasks to process.")
                return []

            log.debug("Got tasks from %s", self.get_url)
            return [ImportTask.from_dict(build) for build in builds[:limit]]
        except Exception as e:
            log.exception("Failed acquire new packages for import:" + str(e))

        return []

    def post_back(self, data_dict):
        """
        Could raise error related to network connection.
        """
        log.debug("Sending back: \n{}".format(json.dumps(data_dict)))
        return post(self.post_back_url, auth=self.auth, data=json.dumps(data_dict), headers=self.headers)

    def post_back_safe(self, data_dict):
        """
        Ignores any error.
        """
        try:
            return self.post_back(data_dict)
        except Exception as e:
            log.error("Failed to post back to frontend : {}".format(data_dict))
            log.exception(str(e))

    def do_import(self, task):
        """
        :type task: ImportTask
        """
        per_task_log_handler = self.setup_per_task_logging(task)
        workdir = tempfile.mkdtemp()

        result = { "build_id": task.build_id }
        try:
            srpm_path = helpers.download_file(
                task.srpm_url,
                workdir
            )

            repo = os.path.join(self.opts.lookaside_location, task.reponame)
            lockfile = os.path.join(repo, "import.lock")
            with helpers.lock(lockfile):
                result.update(import_package(
                    self.opts,
                    task.repo_namespace,
                    task.branches,
                    srpm_path,
                    task.pkg_name,
                ))

        except PackageImportException as e:
            log.exception("Exception raised during package import.")
        finally:
            shutil.rmtree(workdir)

        log.info("sending a response for task {}".format(result))
        self.post_back_safe(result)
        self.teardown_per_task_logging(per_task_log_handler)

    def setup_per_task_logging(self, task):
        handler = logging.FileHandler(
            os.path.join(self.opts.per_task_log_dir,
                         "{0}.log".format(task.build_id))
        )
        handler.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(handler)
        return handler

    def teardown_per_task_logging(self, handler):
        logging.getLogger('').removeHandler(handler)

    def run(self):
        log.info("Importer initialized")

        pool = Pool(workers=3)
        worker_cls = Worker if self.opts.multiple_threads else SingleThreadWorker
        self.is_running = True
        while self.is_running:
            pool.terminate_timeouted(callback=self.post_back_safe)
            pool.remove_dead()

            if pool.busy:
                time.sleep(self.opts.pool_busy_sleep_time)
                continue

            mb_tasks = self.try_to_obtain_new_tasks(exclude=[w.id for w in pool],
                                                    limit=pool.workers - len(pool))

            if not mb_tasks:
                time.sleep(self.opts.sleep_time)
                continue

            for mb_task in mb_tasks:
                p = worker_cls(target=self.do_import, args=[mb_task], id=mb_task.build_id, timeout=3600 * 3)
                pool.append(p)
                log.info("Starting worker '{}' with task '{}' (timeout={})"
                         .format(p.name, mb_task.build_id, p.timeout))
                p.start()


class ImportWorkerManager(WorkerManager):
    """
    Manager taking care of background import workers.
    """

    worker_prefix = 'import_worker'

    def start_task(self, worker_id, task):
        command = [
            "copr-distgit-process-import",
            "--daemon",
            "--build-id", str(task.build_id),
            "--worker-id", worker_id,
        ]
        self.log.info("running worker: %s", " ".join(command))
        self.start_daemon_on_background(command)

    def finish_task(self, worker_id, task_info):
        self.get_task_id_from_worker_id(worker_id)
        return True
