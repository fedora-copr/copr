# coding: utf-8

import pytest
import munch
import rpm

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

from dist_git import helpers
from dist_git.exceptions import RpmSpecParseException, PackageNameCouldNotBeObtainedException


MODULE_REF = 'dist_git.helpers'

@pytest.yield_fixture
def mc_chroot():
    with mock.patch("os.chroot") as handle:
        yield handle


class TestHelpers(object):
    def test_get_rpm_spec_info(self, mc_chroot):
        spec_info = helpers.get_rpm_spec_info('tests/specs/sample.spec')
        dist = rpm.expandMacro('%{dist}')
        assert spec_info == munch.Munch({'release': '1'+dist, 'sources': [], 'epoch': None, 'version': '1.1', 'name': 'sample'})

        with pytest.raises(RpmSpecParseException):
            helpers.get_rpm_spec_info('tests/specs/unparsable.spec')

    def test_get_package_name(self, mc_chroot):
        pkg_name = helpers.get_package_name('tests/specs/sample.spec')
        assert pkg_name == 'sample'

        pkg_name = helpers.get_package_name('tests/specs/unparsable.spec')
        assert pkg_name == 'sample'

        pkg_name = helpers.get_package_name('tests/specs/unparsable_with_macro_in_name.spec')
        assert pkg_name == 'sample-somename'

    def test_get_pkg_evr(self, mc_chroot):
        pkg_evr = helpers.get_pkg_evr('tests/specs/sample.spec')
        assert pkg_evr == '1.1-1'

        pkg_evr = helpers.get_pkg_evr('tests/specs/epoch.spec')
        assert pkg_evr == '3:1.1-1'

        pkg_evr = helpers.get_pkg_evr('tests/specs/unparsable.spec')
        assert not pkg_evr
