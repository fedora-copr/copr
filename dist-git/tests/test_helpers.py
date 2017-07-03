# coding: utf-8

import pytest
import munch

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

from dist_git import helpers


MODULE_REF = 'dist_git.helpers'


@pytest.yield_fixture
def mc_get_spec_data():
    with mock.patch("{}.get_spec_data".format(MODULE_REF)) as handle:
        yield handle


class TestHelpers(object):
    def test_get_pkg_info(self, mc_get_spec_data):
        spec_data = "%global m1 1\nName: foo\nVersion: 1.2\nRelease: %{m1}%{m2}\nEpoch: 3\n"
        mc_get_spec_data.return_value = spec_data
        pkg_info = helpers.get_pkg_info("somepath")
        expected_pkg_info = munch.Munch({
            'nvr': 'foo-1.2-1',
            'envr': '3:foo-1.2-1',
            'epoch': '3',
            'vr': '1.2-1',
            'version': '1.2',
            'release': '1',
            'evr': '3:1.2-1',
            'nv': 'foo-1.2',
            'name': 'foo'
        })
        assert pkg_info == expected_pkg_info

        spec_data = "Name: foo\nVersion: 1.2\nRelease: %mfunc 2\nSources0: http://somesource.src.rpm\n"
        mc_get_spec_data.return_value = spec_data
        pkg_info = helpers.get_pkg_info("somepath")
        expected_pkg_info = munch.Munch({
            'nvr': 'foo-1.2',
            'envr': 'foo-1.2',
            'epoch': '',
            'vr': '1.2',
            'version': '1.2',
            'release': '',
            'evr': '1.2',
            'nv': 'foo-1.2',
            'name': 'foo'
        })
        assert pkg_info == expected_pkg_info

