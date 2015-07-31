# coding: utf-8
import json
import logging

import os
import copy
import tarfile
import tempfile
import shutil
import time
from bunch import Bunch
import pytest

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

from dist_git.dist_git_importer import DistGitImporter, SourceType, ImportTask

MODULE_REF = 'dist_git.dist_git_importer'


@pytest.yield_fixture
def mc_popen():
    with mock.patch(MODULE_REF) as handle:
        yield handle


@pytest.yield_fixture
def mc_get():
    with mock.patch("{}.get".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_post():
    with mock.patch("{}.post".format(MODULE_REF)) as handle:
        yield handle


if False:
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d] %(message)s',
        datefmt='%H:%M:%S'
    )


class TestDistGitImporter(object):
    def setup_method(self, method):
        self.opts = Bunch({
            "frontend_base_url": "http://front",
            "frontend_auth": "secure_password",

        })

        self.dgi = DistGitImporter(self.opts)

        self.USER_NAME = "foo"
        self.PROJECT_NAME = "bar"
        self.BRANCH = "f22"
        self.task_data_1 = {
            "task_id": 123,
            "user": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branch": self.BRANCH,
            "source_type": SourceType.SRPM_LINK,
            "source_json": json.dumps({"url": "http://example.com/pkg.src.rpm"})
        }
        self.task_data_2 = {
            "task_id": 124,
            "user": self.USER_NAME,
            "project": self.PROJECT_NAME,

            "branch": self.BRANCH,
            "source_type": SourceType.SRPM_UPLOAD,
            "source_json": json.dumps({"tmp": "tmp_2", "pkg": "pkg_2.src.rpm"})
        }

        self.task_1 = ImportTask.from_dict(self.task_data_1, self.opts)
        self.task_2 = ImportTask.from_dict(self.task_data_2, self.opts)

    def test_try_to_obtain_new_task_empty(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": []}
        assert self.dgi.try_to_obtain_new_task() is None

    def test_try_to_obtain_handle_error(self, mc_get):
        for err in [IOError, OSError, ValueError]:
            mc_get.side_effect = err
            assert self.dgi.try_to_obtain_new_task() is None

    def test_try_to_obtain_ok(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.task_data_1, self.task_data_2]}
        task = self.dgi.try_to_obtain_new_task()
        assert task.task_id == self.task_data_1["task_id"]
        assert task.user == self.USER_NAME
        assert task.branch == self.BRANCH
        assert task.package_url == "http://example.com/pkg.src.rpm"

    def test_try_to_obtain_ok_2(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.task_data_2, self.task_data_1]}
        task = self.dgi.try_to_obtain_new_task()
        assert task.task_id == self.task_data_2["task_id"]
        assert task.user == self.USER_NAME
        assert task.branch == self.BRANCH
        assert task.package_url == "http://front/tmp/tmp_2/pkg_2.src.rpm"

    def test_try_to_obtain_new_task_unknown_source_type(self, mc_get):
        task_data = copy.deepcopy(self.task_data_1)
        task_data["source_type"] = 999999
        mc_get.return_value.json.return_value = {"builds": [task_data]}
        assert self.dgi.try_to_obtain_new_task() is None
