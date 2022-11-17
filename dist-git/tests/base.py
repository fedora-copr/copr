import os
import shutil
import tempfile
import time

import munch

from copr_dist_git import importer
from copr_dist_git import import_task
from copr_dist_git import import_dispatcher

class Base(object):

    def setup_method(self, method):
        # pylint: disable=attribute-defined-outside-init
        self.tmp_dir_name = self.make_temp_dir()
        self.lookaside_location = os.path.join(self.tmp_dir_name, "lookaside")
        self.per_task_location = os.path.join(self.tmp_dir_name, "per-task-logs")
        os.mkdir(self.per_task_location)
        self.opts = munch.Munch({
            "frontend_base_url": "http://front",
            "frontend_auth": "secure_password",

            "git_base_url": "https://my_git_base_url.org",
            "lookaside_location": self.lookaside_location,

            "cgit_pkg_list_location": self.tmp_dir_name,
            "sleep_time": 10,
            "pool_busy_sleep_time": 0.5,
            "log_dir": self.tmp_dir_name,
            "per_task_log_dir": self.per_task_location,
            "multiple_threads": True,
            "git_user_name": "Test user",
            "git_user_email": "test@test.org",
            "max_workers": 10,
        })

        self.importer = importer.Importer(self.opts)

        self.USER_NAME = "foo"
        self.PROJECT_NAME = "bar"
        self.PACKAGE_NAME = "bar_app"
        self.PACKAGE_VERSION = "2:0.01-1.fc20"
        self.BRANCH = "f22"
        self.BRANCH2 = "f23"
        self.FILE_HASH = "1234abc"

        self.url_task_data = {
            "build_id": 123,
            "owner": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branches": [ self.BRANCH ],
            "srpm_url": "http://example.com/pkg.src.rpm",
            "pkg_name": "pkg",
            "sandbox": "{0}/{1}--{0}".format(self.USER_NAME, self.PROJECT_NAME),
            "background": False,
        }
        self.upload_task_data = {
            "build_id": 124,
            "owner": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branches": [ self.BRANCH ],
            "srpm_url": "http://front/tmp/tmp_2/pkg_2.src.rpm",
            "pkg_name": "pkg_2",
            "sandbox": "{0}/{1}--{0}".format(self.USER_NAME, self.PROJECT_NAME),
            "background": False,
        }

        self.url_task = import_task.ImportTask.from_dict(self.url_task_data)
        self.upload_task = import_task.ImportTask.from_dict(self.upload_task_data)
        self.dispatcher = import_dispatcher.ImportDispatcher(self.opts)
        self.dispatcher.importer = self.importer

    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_{}".format(time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)
        os.mkdir(self.tmp_dir_name)
        return self.tmp_dir_name
