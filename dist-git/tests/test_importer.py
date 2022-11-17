# coding: utf-8

from collections import defaultdict
import json

import os
import copy
import pytest

from munch import Munch
from base import Base

from unittest import mock
from unittest.mock import MagicMock

import copr_dist_git.import_task

MODULE_REF = 'copr_dist_git.importer'


@pytest.yield_fixture
def mc_helpers():
    with mock.patch("{}.helpers".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_worker():
    with mock.patch("{}.Worker".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_import_package():
    with mock.patch("{}.import_package".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_time():
    with mock.patch("{}.time".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_get():
    with mock.patch("{}.get".format(MODULE_REF)) as handle:
        yield handle


@pytest.yield_fixture
def mc_post():
    with mock.patch("{}.post".format(MODULE_REF)) as handle:
        yield handle


class TestImporter(Base):
    def test_try_to_obtain_new_task_empty(self, mc_get):
        mc_get.return_value.json.return_value = []
        assert len(self.importer.try_to_obtain_new_tasks()) is 0

    def test_try_to_obtain_handle_error(self, mc_get):
        for err in [IOError, OSError, ValueError]:
            mc_get.side_effect = err
            assert len(self.importer.try_to_obtain_new_tasks()) is 0

    def test_try_to_obtain_ok(self, mc_get):
        mc_get.return_value.json.return_value = [self.url_task_data, self.upload_task_data]
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.build_id == self.url_task_data["build_id"]
        assert task.owner == self.USER_NAME
        assert self.BRANCH in task.branches
        assert task.srpm_url == "http://example.com/pkg.src.rpm"

    def test_try_to_obtain_ok_2(self, mc_get):
        mc_get.return_value.json.return_value = [self.upload_task_data, self.url_task_data]
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.build_id == self.upload_task_data["build_id"]
        assert task.owner == self.USER_NAME
        assert self.BRANCH in task.branches
        assert task.srpm_url == "http://front/tmp/tmp_2/pkg_2.src.rpm"

    def test_try_to_obtain_new_task_unknown_source_type_ok_3(self, mc_get):
        task_data = copy.deepcopy(self.url_task_data)
        task_data["source_type"] = 999999
        mc_get.return_value.json.return_value = [task_data]
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.build_id == task_data["build_id"]

    def test_post_back(self, mc_post):
        dd = {"foo": "bar"}
        self.importer.post_back(dd)
        assert mc_post.called

    def test_post_back_safe(self, mc_post):
        dd = {"foo": "bar"}
        self.importer.post_back_safe(dd)
        assert mc_post.called
        mc_post.reset_mock()
        assert not mc_post.called

        mc_post.side_effect = IOError
        self.importer.post_back_safe(dd)
        assert mc_post.called

    def test_do_import(self, mc_import_package, mc_helpers):
        mc_helpers.download_file = MagicMock(return_value='somepath.src.rpm')
        mc_import_package.return_value = Munch(
            pkg_name='foo',
            pkg_evr='1.2',
            reponame='foo',
            branch_commits={self.BRANCH: '123', self.BRANCH2: '124'}
        )
        self.importer.post_back_safe = MagicMock()
        self.importer.do_import(self.url_task)

        assert mc_import_package.call_args[0][0] == self.opts
        assert mc_import_package.call_args[0][1] == self.url_task.repo_namespace
        assert mc_import_package.call_args[0][2] == self.url_task.branches
        assert mc_import_package.call_args[0][3] == 'somepath.src.rpm'

        print(self.importer.post_back_safe.has_calls([
            mock.call({'build_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH,
                       'pkg_version': '1.2', 'git_hash': '123', 'repo_name': 'foo'}),
            mock.call({'build_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH2,
                       'pkg_version': '1.2', 'git_hash': '124', 'repo_name': 'foo'})
        ]))


    @mock.patch("copr_dist_git.import_dispatcher.Importer", return_value=MagicMock())
    def test_priorities(self, importer):
        importer.return_value = self.importer
        def _shortener(the_dict):
            return copr_dist_git.import_task.ImportTask.from_dict(
                defaultdict(lambda: "notset", the_dict))
        self.importer.try_to_obtain_new_tasks = MagicMock()
        self.importer.try_to_obtain_new_tasks.return_value = [
            _shortener({"build_id": 1, "sandbox": "a", "background": False}),
            _shortener({"build_id": 2, "sandbox": "a", "background": False}),
            _shortener({"build_id": 3, "sandbox": "b", "background": False}),
            _shortener({"build_id": 3, "sandbox": "c", "background": False}),
            _shortener({"build_id": 1, "sandbox": "a", "background": True}),
        ]
        tasks = self.dispatcher.get_frontend_tasks()
        assert tasks[0].priority == 1
        assert tasks[1].priority == 2
        assert tasks[2].priority == 1
        assert tasks[3].priority == 1
        assert tasks[4].priority == 103


    def test_run(self, mc_time, mc_worker):
        self.importer.try_to_obtain_new_tasks = MagicMock()
        self.importer.do_import = MagicMock()

        def stop_run(*args, **kwargs):
            self.importer.is_running = False

        mc_time.sleep.side_effect = stop_run

        self.importer.try_to_obtain_new_tasks.return_value = None
        self.importer.run()
        assert not mc_worker.called

        self.importer.try_to_obtain_new_tasks.return_value = [self.url_task]
        self.importer.do_import.side_effect = stop_run
        self.importer.run()
        mc_worker.assert_called_with(target=self.importer.do_import, args=[self.url_task],
                                     id=self.url_task.build_id, timeout=mock.ANY)
