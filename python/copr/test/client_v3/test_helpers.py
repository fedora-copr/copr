import pytest
import mock
from munch import Munch
from copr.v3.helpers import wait, succeeded, List
from copr.v3 import BuildProxy, CoprException


class TestHelpers(object):
    def test_succeeded(self):
        b1 = Munch(state="succeeded")
        b2 = Munch(state="succeeded")
        b3 = Munch(state="running")
        b4 = Munch(state="failed")

        assert succeeded(b1)
        assert succeeded([b1, b2])
        assert not succeeded(b3)
        assert not succeeded([b1, b2, b4])


class TestWait(object):
    @mock.patch("copr.v3.proxies.build.BuildProxy.get")
    def test_wait(self, mock_get):
        build = MunchMock(id=1, state="importing")

        mock_get.return_value = MunchMock(id=1, state="succeeded")
        assert wait(build)

        mock_get.return_value = MunchMock(id=1, state="unknown")
        with pytest.raises(CoprException) as ex:
            wait(build)
        assert "Unknown status" in str(ex)

    @mock.patch("copr.v3.proxies.build.BuildProxy.get")
    def test_wait_list(self, mock_get):
        builds = [MunchMock(id=1, state="succeeded"), MunchMock(id=2, state="failed")]
        mock_get.side_effect = lambda id: builds[id-1]
        assert wait(builds)

    @mock.patch("copr.v3.proxies.build.BuildProxy.get")
    def test_wait_custom_list(self, mock_get):
        builds = List([Munch(id=1, state="succeeded"), Munch(id=2, state="failed")], proxy=BuildProxy({}))
        mock_get.side_effect = lambda self, id: builds[id-1]
        assert wait(builds)

    @mock.patch("time.time")
    @mock.patch("copr.v3.proxies.build.BuildProxy.get")
    def test_wait_timeout(self, mock_get, mock_time):
        build = MunchMock(id=1, state="importing")

        mock_get.return_value = MunchMock(id=1, state="running")
        mock_time.return_value = 0
        with pytest.raises(CoprException) as ex:
            wait(build, interval=0, timeout=-10)
        assert "Timeouted" in str(ex)

    @mock.patch("copr.v3.proxies.build.BuildProxy.get")
    def test_wait_callback(self, mock_get):
        build = MunchMock(id=1, state="importing")

        callback = mock.Mock()
        mock_get.return_value = MunchMock(id=1, state="failed")
        wait(build, interval=0, callback=callback)
        assert callback.called


class MunchMock(Munch):
    __proxy__ = BuildProxy({})
