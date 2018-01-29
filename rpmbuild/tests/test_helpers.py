import unittest
from ..copr_rpmbuild.helpers import string2list

class TestHelpers(unittest.TestCase):
    def test_string2list(self):
        self.assertEqual(string2list('foo bar baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('foo,bar,baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('  foo bar\nbaz,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo, \nbar\tbaz,,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo\tbar\tbaz'), ['foo', 'bar', 'baz'])
