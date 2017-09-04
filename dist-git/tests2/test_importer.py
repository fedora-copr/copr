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
def mc_providers_helpers():
    with mock.patch("{}.helpers".format('dist_git.providers')) as handle:
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
    def test_do_import(self, mc_import_package):
        mc_providers_helpers.download_file = MagicMock(return_value='somepath.src.rpm')
        mc_import_package.return_value = Munch(
            pkg_name='foo',
            pkg_evr='1.2',
            reponame='foo',
            branch_commits={self.BRANCH: '123', self.BRANCH2: '124'}
        )
        self.importer.post_back_safe = MagicMock()
        self.importer.do_import(self.url_task)

        print list(mc_import_package.calls())
        assert mc_import_package.call_args[0][0] == self.opts
        assert mc_import_package.call_args[0][1] == self.url_task.repo_namespace
        assert mc_import_package.call_args[0][2] == self.url_task.branches
        assert mc_import_package.call_args[0][3] == 'somepath.src.rpm'

        print self.importer.post_back_safe.has_calls([
            call({'task_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH,
                  'pkg_version': '1.2', 'git_hash': '123', 'repo_name': 'foo'}),
            call({'task_id': 125, 'pkg_name': 'foo', 'branch': self.BRANCH2,
                  'pkg_version': '1.2', 'git_hash': '124', 'repo_name': 'foo'})
        ])
