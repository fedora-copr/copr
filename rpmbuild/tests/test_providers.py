import unittest
import pytest

from copr_rpmbuild.providers import (factory, RubyGemsProvider, PyPIProvider,
                                     UrlProvider)

from copr_rpmbuild.helpers import SourceType


class TestProvidersFactory(unittest.TestCase):
    def setUp(self):
        self.not_existing_source_type = 99

    def test_factory(self):
        self.assertEqual(factory(SourceType.RUBYGEMS), RubyGemsProvider)
        self.assertEqual(factory(SourceType.PYPI), PyPIProvider)
        self.assertEqual(factory(SourceType.LINK), UrlProvider)
        with pytest.raises(RuntimeError):
            factory(self.not_existing_source_type)
