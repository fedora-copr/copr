#!/usr/bin/python

import os
import json
import time
import logging

from requests import get, post

from package_import import import_package
from process_pool import Worker, Pool
from exceptions import PackageImportException
from providers import PackageContentProviderFactory
from import_task import ImportTask

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

    def try_to_obtain_new_tasks(self, exclude=[], limit=1):
        log.debug("Get task data...")
        try:
            # get the data
            r = get(self.get_url)
            # take the first task
            builds = filter(lambda x: x["task_id"] not in exclude, r.json()["builds"])
            if not builds:
                log.debug("No new tasks to process.")

            return [ImportTask.from_dict(build) for build in builds]
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

    def get_result_dict_for_frontend(self, task_id, branch, result):
        if not result or not branch in result.branch_commits:
            return {
                "task_id": task_id,
                "error": "Could not import this branch.",
                "branch": branch,
            }

        return {
            "task_id": task_id,
            "pkg_name": result.pkg_name,
            "pkg_version": result.pkg_evr,
            "repo_name": result.reponame,
            "git_hash": result.branch_commits[branch],
            "branch": branch,
        }

    def do_import(self, task):
        """
        :type task: ImportTask
        """
        per_task_log_handler = self.setup_per_task_logging(task)

        provider = PackageContentProviderFactory.getInstance(task, self.opts)
        result = None
        try:
            package_content = provider.get_content(task)
            result = import_package(
                self.opts,
                task.repo_namespace,
                task.branches,
                package_content
            )
        except PackageImportException as e:
            log.exception("Exception raised during package import.")
        finally:
            provider.cleanup()

        log.info("sending a responses for branches {0}".format(', '.join(task.branches)))
        for branch in task.branches:
            self.post_back_safe(
                self.get_result_dict_for_frontend(task.task_id, branch, result)
            )

        self.teardown_per_task_logging(per_task_log_handler)

    def setup_per_task_logging(self, task):
        # Avoid putting logs into subdirectories
        # when dist git branch name contains slashes.
        task_id = str(task.task_id).replace('/', '_')

        handler = logging.FileHandler(
            os.path.join(self.opts.per_task_log_dir,
                         "{0}.log".format(task_id))
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
                p = worker_cls(target=self.do_import, args=[mb_task], id=mb_task.task_id, timeout=3600)
                pool.append(p)
                log.info("Starting worker '{}' with task '{}' (timeout={})"
                         .format(p.name, mb_task.task_id, p.timeout))
                p.start()
