"""
Test all kind of build chroot request via APIv3
"""

import pytest
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator
from coprs.logic.builds_logic import BuildChrootResultsLogic


class TestAPIv3BuildChrootsResults(CoprsTestCase):
    """
    Tests related to build chroots results
    """

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    def test_build_chroot_built_packages(self):
        """
        Test the endpoint for getting built packages (NEVRA dicts) for a given
        build chroot.
        """
        self.db.session.add(self.b1, self.b1_bc)
        built_packages = {
            "packages": [
                {
                    "name": "hello",
                    "epoch": 0,
                    "version": "2.8",
                    "release": "1.fc33",
                    "arch": "x86_64"
                },
            ]
        }
        BuildChrootResultsLogic.create_from_dict(
            self.b1.build_chroots[0], built_packages)
        self.db.session.commit()

        endpoint = "/api_3/build-chroot/built-packages/"
        endpoint += "?build_id={build_id}&chrootname={chrootname}"
        params = {"build_id": self.b1.id, "chrootname": "fedora-18-x86_64"}

        result = self.tc.get(endpoint.format(**params))
        assert result.is_json
        assert result.json == built_packages


    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    @pytest.mark.parametrize("order", ["ASC", "DESC"])
    def test_build_chroot_list(self, order):
        """
        Test listing of chroots.
        """
        endpoint = "/api_3/build-chroot/list/3?order_type={}".format(order)
        result = self.tc.get(endpoint)
        item1 = {
            'ended_on': None,
            'name': 'fedora-17-x86_64',
            'result_url': 'http://copr-be-dev.cloud.fedoraproject.org/results/user2/foocopr/fedora-17-x86_64/bar/',
            'started_on': None,
            'state': 'waiting'
        }
        item2 = {
            'ended_on': None,
            'name': 'fedora-17-i386',
            'result_url': 'http://copr-be-dev.cloud.fedoraproject.org/results/user2/foocopr/fedora-17-i386/bar/',
            'started_on': None,
            'state': 'waiting'
        }
        expected = [item1, item2] if order == "ASC" else [item2, item1]
        assert result.json["items"] == expected


    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_coprs",
                             "f_mock_chroots", "f_builds", "f_db")
    def test_build_chroot_list_no_id(self):
        """
        Get list of chroots, missing build_id
        """
        endpoint = "/api_3/build-chroot/list"
        result = self.tc.get(endpoint)
        assert result.json == {'error': 'Missing argument build_id'}
        assert result.status_code == 400
