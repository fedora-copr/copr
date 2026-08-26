# pylint: disable=no-self-use

from unittest import mock
from tests.coprs_test_case import CoprsTestCase
from coprs import app
from coprs.auth import GroupAuth, LDAPGroups


class TestGroupAuth(CoprsTestCase):

    @mock.patch("coprs.auth.LDAP.get_user_groups")
    def test_group_names_ldap(self, get_user_groups):
        """
        Test that we can parse LDAP response containing user groups and return
        just their names
        """

        app.config["FAS_LOGIN"] = False
        app.config["LDAP_URL"] = "not-important"
        app.config["LDAP_SEARCH_STRING"] = "not-important"

        # We expect `LDAP.get_user_groups` to return something like this.
        # Some internal values were redacted but otherwise it's a copy-pasted
        # response
        get_user_groups.return_value = [
            b'cn=group1,cn=groups,ou=foo,dc=company,dc=com',
            b'cn=group2,cn=groups,ou=bar,dc=company,dc=com',
            b'cn=another-group,cn=groups,ou=baz,ou=qux,dc=company,dc=com',
            b'ipaUniqueID=ba3ba98a-a12d-11f1-af9d-f691a8b0dc3a,cn=hbac,dc=domain,dc=example,dc=com',
            b'cn=somerole,cn=roles,cn=accounts,dc=domain,dc=example,dc=com',
            b'cn=another-group-2,cn=groups,ou=foo,ou=bar,dc=company,dc=com'
        ]
        user = mock.MagicMock()
        GroupAuth.update_user_groups(user, LDAPGroups.group_names(user.username))
        assert user.openid_groups == {
            "fas_groups": ["group1", "group2", "another-group",
                           "another-group-2"]}
