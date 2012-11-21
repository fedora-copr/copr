import flask

from tests.coprs_test_case import CoprsTestCase

class TestCoprsShow(CoprsTestCase):
    def test_show_no_entries(self):
        assert 'No entries' in self.tc.get('/').data

    def test_show_more_entries(self, f_users, f_coprs):
        r = self.tc.get('/')
        assert r.data.count('<div class=copr>') == 3

class TestCoprsOwned(CoprsTestCase):
    def test_owned_none(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            r = c.get('/coprs/owned/{0}/'.format(self.u3.name))
            assert r.data.find('No entries') != -1

    def test_owned_one(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            r = c.get('/coprs/owned/{0}/'.format(self.u1.name))
            assert r.data.count('<div class=copr>') == 1

class TestCoprsAllowed(CoprsTestCase):
    def test_allowed_none(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            r = c.get('/coprs/allowed/{0}/'.format(self.u3.name))
            assert r.data.find('No entries') != -1

    def test_allowed_one(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            r = c.get('/coprs/allowed/{0}/'.format(self.u1.name))
            assert r.data.count('<div class=copr>') == 1

    def test_allowed_one_but_asked_for_one_more(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            r = c.get('/coprs/allowed/{0}/'.format(self.u2.name))
            assert r.data.count('<div class=copr>') == 1

class TestCoprNew(CoprsTestCase):
    def test_copr_new_normal(self, f_users):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            r = c.post('/coprs/new/', data = {'name': 'foo', 'release': 'fedora-rawhide', 'arches': ['i386']}, follow_redirects = True)
            assert self.models.Copr.query.filter(self.models.Copr.name == 'foo').first()
            assert "New entry was successfully posted" in r.data

    def test_copr_new_exists_for_another_user(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == 'foocopr').all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': 'foocopr', 'release': 'fedora-rawhide', 'arches': ['i386']}, follow_redirects = True)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == 'foocopr').all()) == foocoprs + 1
            assert "New entry was successfully posted" in r.data

    def test_copr_new_exists_for_this_user(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == 'foocopr').all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': 'foocopr', 'release': 'fedora-rawhide', 'arches': ['i386']}, follow_redirects = True)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == 'foocopr').all()) == foocoprs
            assert "You already have copr named" in r.data
