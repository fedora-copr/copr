import flask

from tests.coprs_test_case import CoprsTestCase

class TestCoprShowBuilds(CoprsTestCase):
    def test_copr_show_builds(self, f_users, f_coprs, f_builds):
        r = self.tc.get('/coprs/detail/{0}/{1}/builds/'.format(self.u2.name, self.c2.name))
        print r.data
        assert r.data.count('<tr class=build-') == 2

class TestCoprAddBuild(CoprsTestCase):
    def test_copr_owner_can_add_build(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.c1])
            r = c.post('/coprs/detail/{0}/{1}/add_build/'.format(self.u1.name, self.c1.name),
                      data = {'pkgs': 'http://foo.bar'},
                      follow_redirects = True)
            assert len(self.models.Build.query.all()) == 1
