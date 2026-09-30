# pylint: disable=no-self-use

from unittest import mock

import ldap
import pytest

from tests.coprs_test_case import CoprsTestCase
from coprs import app
from coprs.auth import GroupAuth, LDAP, LDAPGroups
from coprs.exceptions import CoprHttpException


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


class TestLDAP(CoprsTestCase):

    @mock.patch("coprs.auth.ldap.initialize")
    def test_server_down_fails_immediately(self, initialize):
        """
        A LDAP server that is down must fail the log-in right away, not spin
        in an endless retry loop
        """
        error = ldap.SERVER_DOWN({"desc": "Can't contact LDAP server"})
        initialize.return_value.search_s.side_effect = error

        client = LDAP("ldap://not-important", "ou=users,dc=example,dc=com")
        with pytest.raises(CoprHttpException) as ex:
            client.get_user("someuser")

        assert "Can't contact LDAP server" in str(ex.value)
        assert ex.value.code == 503
        assert initialize.call_count == 1
        initialize.return_value.unbind_s.assert_called_once()

    @mock.patch("coprs.auth.ldap.initialize")
    def test_timeout_is_an_outage_too(self, initialize):
        """
        Hitting LDAP_TIMEOUT must end up as CoprHttpException, the same way
        an unreachable server does.  Note that ldap.TIMEOUT has no args.
        """
        initialize.return_value.search_s.side_effect = ldap.TIMEOUT()

        client = LDAP("ldap://not-important", "ou=users,dc=example,dc=com")
        with pytest.raises(CoprHttpException) as ex:
            client.get_user("someuser")

        assert ex.value.code == 503
        assert "unknown error" in str(ex.value)

    @mock.patch("coprs.auth.ldap.initialize")
    def test_timeouts_are_set(self, initialize):
        """
        Both the connect and the query timeout need to be limited, otherwise
        a non-responding server blocks the request for minutes
        """
        app.config["LDAP_TIMEOUT"] = 10
        initialize.return_value.search_s.return_value = []

        client = LDAP("ldap://not-important", "ou=users,dc=example,dc=com")
        assert client.get_user_groups("someuser") == []

        timeouts = {}
        for call in initialize.return_value.set_option.call_args_list:
            option, value = call.args
            assert 0 < value <= 10
            timeouts.setdefault(option, value)
        assert set(timeouts) == {ldap.OPT_NETWORK_TIMEOUT, ldap.OPT_TIMEOUT}

    @mock.patch("coprs.auth.ldap.initialize")
    def test_timeout_budget_is_shared(self, initialize):
        """
        The whole lookup must fit into LDAP_TIMEOUT.  A slow bind shortens the
        timeout left for the query itself.
        """
        app.config["LDAP_TIMEOUT"] = 10
        initialize.return_value.search_s.return_value = []

        # deadline, the timeout for connect+bind, and the one after the bind
        with mock.patch("coprs.auth.time.monotonic", side_effect=[0, 0, 6]):
            client = LDAP("ldap://not-important", "ou=users,dc=example,dc=com")
            assert client.get_user_groups("someuser") == []

        # The last OPT_TIMEOUT set before search_s() is the remaining budget
        option, value = initialize.return_value.set_option.call_args_list[-1].args
        assert option == ldap.OPT_TIMEOUT
        assert value == 4
