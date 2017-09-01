# coding: utf-8

import json

import os
import copy
import pytest

from bunch import Bunch
from mock import call
from munch import Munch

from base import Base

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


MODULE_REF = 'dist_git.importer'


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
        mc_get.return_value.json.return_value = {"builds": []}
        assert len(self.importer.try_to_obtain_new_tasks()) is 0

    def test_try_to_obtain_handle_error(self, mc_get):
        for err in [IOError, OSError, ValueError]:
            mc_get.side_effect = err
            assert len(self.importer.try_to_obtain_new_tasks()) is 0

    def test_try_to_obtain_ok(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.url_task_data, self.upload_task_data]}
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.task_id == self.url_task_data["task_id"]
        assert task.user == self.USER_NAME
        assert self.BRANCH in task.branches
        assert task.source_data['url'] == "http://example.com/pkg.src.rpm"

    def test_try_to_obtain_ok_2(self, mc_get):
        mc_get.return_value.json.return_value = {"builds": [self.upload_task_data, self.url_task_data]}
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.task_id == self.upload_task_data["task_id"]
        assert task.user == self.USER_NAME
        assert self.BRANCH in task.branches
        assert task.source_data['url'] == "http://front/tmp/tmp_2/pkg_2.src.rpm"

    def test_try_to_obtain_new_task_unknown_source_type_ok_3(self, mc_get):
        task_data = copy.deepcopy(self.url_task_data)
        task_data["source_type"] = 999999
        mc_get.return_value.json.return_value = {"builds": [task_data]}
        task = self.importer.try_to_obtain_new_tasks()[0]
        assert task.task_id == task_data["task_id"]

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

    def test_do_import(self, mc_import_package):
        # todo
        """
        mc_providers_helpers.download_file = MagicMock(return_value='pkg.spec')
        mc_import_package.return_value = Munch(
            pkg_name='foo',
            pkg_evr='1.2',
            reponame='foo',
            branch_commits={self.BRANCH: '123', self.BRANCH2: '124'}
        )
        self.importer.post_back_safe = MagicMock()
        self.importer.do_import(self.spec_task)

        assert mc_import_package.call_args[0][0] == self.opts
        assert mc_import_package.call_args[0][1] == self.spec_task.repo_namespace
        assert mc_import_package.call_args[0][2] == self.spec_task.branches
        assert mc_import_package.call_args[0][3] == providers.PackageContent({'spec_path': 'pkg.spec'})

        print self.importer.post_back_safe.has_calls([
            call({'task_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH,
                  'pkg_version': '1.2', 'git_hash': '123', 'repo_name': 'foo'}),
            call({'task_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH2,
                  'pkg_version': '1.2', 'git_hash': '124', 'repo_name': 'foo'})
        ])
        """

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
                                     id=self.url_task.task_id, timeout=mock.ANY)
