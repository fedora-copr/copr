from unittest import TestCase

from copr_common.helpers import format_evr


class TestFormatEvr(TestCase):

    def test_without_epoch(self):
        self.assertEqual(format_evr(None, "1.0", "1.fc40"), "1.0-1.fc40")

    def test_with_int_epoch(self):
        self.assertEqual(format_evr(1, "1.0", "1.fc40"), "1:1.0-1.fc40")

    def test_with_string_epoch(self):
        self.assertEqual(format_evr("2", "1.0", "1.fc40"), "2:1.0-1.fc40")
