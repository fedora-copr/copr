import unittest
from ..main import DistGitProvider


class TestDistGitProvider(unittest.TestCase):
    def test_init(self):
        source_json = {"clone_url": "https://src.fedoraproject.org/git/rpms/389-admin-console.git", "branch": "f25"}
        provider = DistGitProvider(source_json)
        self.assertEqual(provider.clone_url, "https://src.fedoraproject.org/git/rpms/389-admin-console.git")
        self.assertEqual(provider.branch, "f25")
