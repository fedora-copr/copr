import unittest
import pytest

from copr_common.enums import BuildSourceEnum

from copr_rpmbuild.providers import (factory, RubyGemsProvider, PyPIProvider,
                                     UrlProvider)


class TestProvidersFactory(unittest.TestCase):
    def setUp(self):
        self.not_existing_source_type = 99

    def test_factory(self):
        self.assertEqual(factory(BuildSourceEnum.rubygems), RubyGemsProvider)
        self.assertEqual(factory(BuildSourceEnum.pypi), PyPIProvider)
        self.assertEqual(factory(BuildSourceEnum.link), UrlProvider)
        with pytest.raises(RuntimeError):
            factory(self.not_existing_source_type)
