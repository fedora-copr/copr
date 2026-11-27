"""
Tests for 'projects-in-storage'
"""

import pytest
from copr_common.enums import StorageEnum
from tests.coprs_test_case import CoprsTestCase
from commands.projects_in_storage import projects_in_storage


class TestProjectsInStorage(CoprsTestCase):
    @pytest.mark.usefixtures("f_users", "f_groups", "f_coprs", "f_group_copr",
                             "f_mock_chroots", "f_db")
    def test_projects_in_storage(self, capsys):
        self.c1.storage = StorageEnum.pulp
        self.db.session.commit()

        projects_in_storage.callback(storage="pulp")
        out = capsys.readouterr().out.splitlines()
        assert out == ["user1/foocopr"]

        projects_in_storage.callback(storage="backend")
        out = capsys.readouterr().out.splitlines()
        assert out == ["@group1/groupcopr1", "@group1/groupcopr2",
                       "user2/barcopr", "user2/foocopr"]
