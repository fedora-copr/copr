import unittest
import tempfile
import shutil
import os

from copr_rpmbuild.helpers import string2list, locate_srpm

class TestHelpers(unittest.TestCase):
    def test_string2list(self):
        self.assertEqual(string2list('foo bar baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('foo,bar,baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('  foo bar\nbaz,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo, \nbar\tbaz,,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo\tbar\tbaz'), ['foo', 'bar', 'baz'])

    def test_locate_srpm(self):
        tmpdir = tempfile.mkdtemp(prefix="copr-rpmbuild-test-")
        srpm_path = os.path.join(tmpdir, "dummy.src.rpm")
        open(srpm_path, "w").close()
        self.assertEqual(srpm_path, locate_srpm(tmpdir))
        shutil.rmtree(tmpdir)
