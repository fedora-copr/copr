"""
Test all kinds of package request via v3 API
"""

import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestAPIv3Packages(CoprsTestCase):

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs", "f_db")
    def test_v3_package_pypi(self):
        response = self.api3.create_pypi_package(
            "foocopr",
            "pello1",
            options={"spec_generator": "pyp2spec"},
        )
        assert response.status_code == 200

        with pytest.raises(AssertionError):
            response = self.api3.create_pypi_package(
                "foocopr",
                "pello2",
                options={"spec_generator": "pyp2rpm"},
            )
