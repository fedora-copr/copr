"""Tests for built package search."""

import pytest

from coprs.logic.builds_logic import BuildChrootResultsLogic
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestPackageSearch(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds", "f_db")
    def test_search_by_name_and_arch(self):
        self.db.session.add(self.b1)

        built_packages = {
            "packages": [
                {
                    "name": "git",
                    "epoch": 0,
                    "version": "2.32.0",
                    "release": "1.fc36",
                    "arch": "x86_64",
                },
            ]
        }
        BuildChrootResultsLogic.create_from_dict(
            self.b1.build_chroots[0],
            built_packages,
        )
        self.db.session.commit()

        response = self.test_client.get(
            "/coprs/packages/search/?name=git&arch=x86_64"
        )
        assert response.status_code == 200
        assert b"git" in response.data
        assert str(self.b1.id).encode("utf-8") in response.data
