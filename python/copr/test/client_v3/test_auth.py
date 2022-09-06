import time
import pytest
from copr.v3.auth import ApiToken, Gssapi, auth_from_config, CoprAuthException
from copr.v3.auth.base import BaseAuth
from copr.test import mock


class TestApiToken:
    @staticmethod
    def test_make_expensive():
        """
        Test that `ApiToken` load all necessary information from config
        """
        config = mock.MagicMock()
        auth = ApiToken(config)
        # Make sure all auth values are loaded from the config
        assert auth.auth
        assert auth.username


class TestGssApi:
    @staticmethod
    @mock.patch("requests.get")
    def test_make_expensive(mock_get):
        """
        Test that `Gssapi` knows what to do with information from Kerberos
        """
        config = mock.MagicMock()
        auth = Gssapi(config)
        assert not auth.username
        assert not auth.auth

        # Fake a response from Kerberos
        response = mock.MagicMock()
        response.json.return_value = {"id": 123, "name": "jdoe"}
        response.cookies = {"session": "foo-bar-hash"}
        mock_get.return_value = response

        # Make sure GSSAPI cookies are set
        auth.make_expensive()
        assert auth.username == "jdoe"
        assert auth.cookies == {"session": "foo-bar-hash"}


class TestBaseAuth:
    @staticmethod
    @mock.patch("copr.v3.auth.base.BaseAuth.expired")
    @mock.patch("copr.v3.auth.base.BaseAuth.make_expensive")
    def test_make_without_cache(make_expensive, _expired):
        """
        Test that auth classes remember and re-use the information from
        `make_expensive()`
        """
        auth = BaseAuth(config=None)
        auth.cache = mock.MagicMock()

        # Even though we call make() multiple times,
        # make_expensive() is called only once
        for _ in range(5):
            auth.make()
        assert make_expensive.call_count == 1

    @staticmethod
    @mock.patch("copr.v3.auth.base.BaseAuth.make_expensive")
    def test_make_reauth(make_expensive):
        """
        When reauth is requested, make sure we don't use any previous tokens
        """
        auth = BaseAuth(config=None)
        auth.cache = mock.MagicMock()
        for _ in range(5):
            auth.make(reauth=True)
        assert make_expensive.call_count == 5

    @staticmethod
    @mock.patch("copr.v3.auth.base.BaseAuth.make_expensive")
    def test_make_from_cache(make_expensive):
        """
        If there is a cached session cookie that is still valid, use it and
        don't make any expensive calls
        """
        auth = BaseAuth(config=None)
        auth.cache = FakeCache(None)
        for _ in range(5):
            auth.make()
        assert make_expensive.call_count == 0

    @staticmethod
    @mock.patch("copr.v3.auth.base.BaseAuth.make_expensive")
    def test_make_from_cache_expired(make_expensive):
        """
        If there is a cached session cookie but it is expired, just ignore it
        """
        auth = BaseAuth(config=None)
        auth.cache = FakeCacheExpired(None)
        for _ in range(5):
            auth.make()
        assert make_expensive.call_count == 1


class TestAuth:
    @staticmethod
    def test_auth_from_config():
        """
        Make sure we use the expected authentication method
        """
        # Use (login, token) authentication if there is enough information
        auth = auth_from_config({
            "copr_url": "http://copr",
            "login": "test",
            "token": "test",
            "username": "jdoe",
        })
        assert isinstance(auth, ApiToken)

        # Otherwise use GSSAPI (if gssapi is enabled, which is by default)
        auth = auth_from_config({
            "copr_url": "http://copr",
            "gssapi": True,
        })
        assert isinstance(auth, Gssapi)

        # There are no other authentication methods
        config = {
            "copr_url": "http://copr",
            "gssapi": False,
        }
        with pytest.raises(CoprAuthException):
            auth = auth_from_config(config)


class FakeCache(mock.MagicMock):
    # pylint: disable=too-many-ancestors
    def load_session(self):
        # pylint: disable=no-self-use
        return {
            "name": "jdoe",
            "session": "foo-bar-hash",
            "expiration": time.time() + 1
        }

class FakeCacheExpired(FakeCache):
    # pylint: disable=too-many-ancestors
    def load_session(self):
        return {
            "name": "jdoe",
            "session": "foo-bar-hash",
            "expiration": time.time() - 1
        }
