from tests.coprs_test_case import CoprsTestCase

class TestCoprsShow(CoprsTestCase):
    def test_show_no_entries(self):
        assert 'No entries here so far' in self.tc.get('/').data

    def test_show_one_entry(self, f_data1):
        r = self.tc.get('/')
        assert r.data.count('<div class=copr>') == 1
