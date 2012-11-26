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

            self.db.session.add(self.u3)
            r = c.get('/coprs/owned/{0}/'.format(self.u3.name))
            assert 'No entries' in r.data

    def test_owned_one(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/owned/{0}/'.format(self.u1.name))
            assert r.data.count('<div class=copr>') == 1

class TestCoprsAllowed(CoprsTestCase):
    def test_allowed_none(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            self.db.session.add(self.u3)
            r = c.get('/coprs/allowed/{0}/'.format(self.u3.name))
            assert 'No entries' in r.data

    def test_allowed_one(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/allowed/{0}/'.format(self.u1.name))
            assert r.data.count('<div class=copr>') == 1

    def test_allowed_one_but_asked_for_one_more(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/allowed/{0}/'.format(self.u1.name))
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

            self.db.session.add(self.c1)
            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': self.c1.name, 'release': 'fedora-rawhide', 'arches': ['i386']}, follow_redirects = True)
            self.db.session.add(self.c1)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all()) == foocoprs + 1
            assert "New entry was successfully posted" in r.data

    def test_copr_new_exists_for_this_user(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.c1)
            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': self.c1.name, 'release': 'fedora-rawhide', 'arches': ['i386']}, follow_redirects = True)
            self.db.session.add(self.c1)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all()) == foocoprs
            assert "You already have copr named" in r.data

class TestCoprDetail(CoprsTestCase):
    def test_copr_detail_not_found(self):
        r = self.tc.get('/coprs/detail/foo/bar/')
        assert r.status_code == 404

    def test_copr_detail_normal(self, f_users, f_coprs):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u1.name, self.c1.name))
        assert r.status_code == 200
        assert self.c1.name in r.data

    def test_copr_detail_contains_builds(self, f_users, f_coprs, f_builds):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u1.name, self.c1.name))
        assert r.data.count('<tr class=build') == 2

    def test_copr_detail_contains_permissions(self, f_users, f_coprs, f_copr_permissions):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c3.name))
        assert '<table class=permissions' in r.data
        assert '<tr><td>{0}'.format(self.u3.name) in r.data
        assert '<tr><td>{0}'.format(self.u1.name) in r.data

    def test_copr_detail_doesnt_contain_forms_for_anonymous_user(self, f_users, f_coprs):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c3.name))
        assert '<form' not in r.data

    def test_copr_detail_allows_asking_for_building(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c2.name))
            assert '<input type=submit value="Apply for building">' in r.data

    def test_copr_detail_doesnt_allow_owner_to_ask_for_building(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c2.name))
            assert '<input type=submit value="Apply for building">' not in r.data

    def test_copr_detail_allows_giving_up_building(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c2.name))
            assert '<input type=submit value="Give up building">' in r.data

class TestCoprEdit(CoprsTestCase):
    def test_edit_prefills_id(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.c1])
            r = c.get('/coprs/detail/{0}/{1}/edit/'.format(self.u1.name, self.c1.name))
            # TODO: use some kind of html parsing library to look for the hidden input, this ties us
            # to the precise format of the tag
            assert '<input hidden id="id" name="id" type="hidden" value="{0}">'.format(self.c1.id) in r.data

    def test_edit_has_correct_permissions_form(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.get('/coprs/detail/{0}/{1}/edit/'.format(self.u2.name, self.c3.name))
            assert '<input id="user_3" name="user_3" type="checkbox" value="y">' in r.data
            assert '<input id="user_1" name="user_1" type="checkbox" value="y">' in r.data


class TestCoprUpdate(CoprsTestCase):
    def test_update_no_changes(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.c1])
            r = c.post('/coprs/detail/{0}/{1}/update/'.format(self.u1.name, self.c1.name),
                       data = {'name': self.c1.name, 'release': self.c1.release, 'arches': self.c1.arches, 'id': self.c1.id},
                       follow_redirects = True)
            assert 'Copr was updated successfully' in r.data

class TestCoprApplyForBuilding(CoprsTestCase):
    def test_apply(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u1, self.u2, self.c1])
            r = c.post('/coprs/detail/{0}/{1}/apply_for_building/'.format(self.u1.name, self.c1.name),
                       follow_redirects = True)
            assert 'You have successfuly applied' in r.data

            self.db.session.add_all([self.u1, self.u2, self.c1])
            new_perm = self.models.CoprPermission.query.filter(self.models.CoprPermission.user_id == self.u2.id).\
                                                        filter(self.models.CoprPermission.copr_id == self.c1.id).\
                                                        first()
            assert not new_perm.copr_builder

class TestCoprGiveUpBuilding(CoprsTestCase):
    def test_give_up(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.u2, self.c2])
            r = c.post('/coprs/detail/{0}/{1}/give_up_building/'.format(self.u2.name, self.c2.name),
                       follow_redirects = True)
            assert 'You have successfuly given up' in r.data

            self.db.session.add_all([self.u1, self.u2, self.c2])
            exists = self.models.CoprPermission.query.filter(self.models.CoprPermission.user_id == self.u1.id).\
                                                      filter(self.models.CoprPermission.copr_id == self.c2.id).\
                                                      first()
            assert not exists

class TestCoprUpdatePermissions(CoprsTestCase):
    def test_cancel_permission(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2])
            # Although it shouldn't be needed, preset some data: https://github.com/ajford/flask-wtf/issues/55
            r = c.post('/coprs/detail/{0}/{1}/update_permissions/'.format(self.u2.name, self.c2.name),
                       data = {'csrf_token': u'20121123111948##1653cb2ef73cb9f7b4670472df7354416e61cf2d'},
                       follow_redirects = True)
            self.db.session.add_all([self.u1])
            assert '<tr><td>{0}</td><td>{1}</td></tr>'.format(self.u1.name, 'True') not in r.data

    def test_update_more_permissions(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.post('/coprs/detail/{0}/{1}/update_permissions/'.format(self.u2.name, self.c3.name),
                       data = {'user_1': 'y', 'user_3': 'y'},
                       follow_redirects = True)
            self.db.session.add_all([self.u1, self.u3])
            assert '<tr><td>{0}</td><td>{1}</td></tr>'.format(self.u1.name, 'True') in r.data
            assert '<tr><td>{0}</td><td>{1}</td></tr>'.format(self.u3.name, 'True') in r.data
