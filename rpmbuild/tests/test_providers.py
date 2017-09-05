import unittest
from ..copr_rpmbuild.providers import factory, DistGitProvider, RubyGemsProvider, PyPIProvider
from ..copr_rpmbuild.helpers import SourceType


class TestProvidersFactory(unittest.TestCase):
    def setUp(self):
        self.not_existing_source_type = 99

    def test_factory(self):
        self.assertEqual(factory(SourceType.DISTGIT), DistGitProvider)
        self.assertEqual(factory(SourceType.RUBYGEMS), RubyGemsProvider)
        self.assertEqual(factory(SourceType.PYPI), PyPIProvider)
        with self.assertRaises(RuntimeError):
            factory(self.not_existing_source_type)
