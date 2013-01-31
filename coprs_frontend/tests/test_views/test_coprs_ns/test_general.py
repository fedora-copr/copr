import flask

from tests.coprs_test_case import CoprsTestCase

class TestCoprsShow(CoprsTestCase):
    def test_show_no_entries(self):
        assert 'No coprs...' in self.tc.get('/').data

    def test_show_more_entries(self, f_users, f_coprs):
        r = self.tc.get('/')
        assert r.data.count('<div class="copr">') == 3

class TestCoprsOwned(CoprsTestCase):
    def test_owned_none(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            self.db.session.add(self.u3)
            r = c.get('/coprs/owned/{0}/'.format(self.u3.name))
            assert 'No coprs...' in r.data

    def test_owned_one(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/owned/{0}/'.format(self.u1.name))
            assert r.data.count('<div class="copr">') == 1

class TestCoprsAllowed(CoprsTestCase):
    def test_allowed_none(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            self.db.session.add(self.u3)
            r = c.get('/coprs/allowed/{0}/'.format(self.u3.name))
            assert 'No coprs...' in r.data

    def test_allowed_one(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/allowed/{0}/'.format(self.u1.name))
            assert r.data.count('<div class="copr">') == 1

    def test_allowed_one_but_asked_for_one_more(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.u1)
            r = c.get('/coprs/allowed/{0}/'.format(self.u1.name))
            assert r.data.count('<div class="copr">') == 1

class TestCoprNew(CoprsTestCase):
    success_string = 'New copr was successfully created'

    def test_copr_new_normal(self, f_users, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            r = c.post('/coprs/new/', data = {'name': 'foo', 'fedora-rawhide-i386': 'y', 'arches': ['i386']}, follow_redirects = True)
            assert self.models.Copr.query.filter(self.models.Copr.name == 'foo').first()
            assert self.success_string in r.data

            # make sure no initial build was submitted
            assert self.models.Build.query.first() == None

    def test_copr_new_exists_for_another_user(self, f_users, f_coprs, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u3.openid_name

            self.db.session.add(self.c1)
            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': self.c1.name, 'fedora-rawhide-i386': 'y'}, follow_redirects = True)
            print r.data
            self.db.session.add(self.c1)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all()) == foocoprs + 1
            assert self.success_string in r.data

    def test_copr_new_exists_for_this_user(self, f_users, f_coprs, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add(self.c1)
            foocoprs = len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all())
            assert foocoprs > 0

            r = c.post('/coprs/new/', data = {'name': self.c1.name, 'fedora-rawhide-i386': 'y'}, follow_redirects = True)
            self.db.session.add(self.c1)
            assert len(self.models.Copr.query.filter(self.models.Copr.name == self.c1.name).all()) == foocoprs
            assert "You already have copr named" in r.data

    def test_copr_new_with_initial_pkgs(self, f_users, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            r = c.post('/coprs/new/', data = {'name': 'foo', 'fedora-rawhide-i386': 'y', 'initial_pkgs': ['http://f', 'http://b']}, follow_redirects = True)
            copr = self.models.Copr.query.filter(self.models.Copr.name == 'foo').first()
            assert copr
            assert self.success_string in r.data

            assert self.models.Build.query.first().copr == copr
            assert copr.build_count == 1
            assert 'Initial packages were successfully submitted' in r.data

class TestCoprDetail(CoprsTestCase):
    def test_copr_detail_not_found(self):
        r = self.tc.get('/coprs/detail/foo/bar/')
        assert r.status_code == 404

    def test_copr_detail_normal(self, f_users, f_coprs):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u1.name, self.c1.name))
        assert r.status_code == 200
        assert self.c1.name in r.data

    def test_copr_detail_contains_builds(self, f_users, f_coprs, f_builds):
        r = self.tc.get('/coprs/detail/{0}/{1}/builds/'.format(self.u1.name, self.c1.name))
        print r.data
        assert r.data.count('<tr class="build') == 2

    def test_copr_detail_anonymous_doesnt_contain_permissions_table_when_no_permissions(self, f_users, f_coprs, f_copr_permissions):
        r = self.tc.get('/coprs/detail/{0}/{1}/permissions/'.format(self.u1.name, self.c1.name))
        assert '<table class="permissions"' not in r.data

    def test_copr_detail_contains_permissions_table(self, f_users, f_coprs, f_copr_permissions):
        r = self.tc.get('/coprs/detail/{0}/{1}/permissions/'.format(self.u2.name, self.c3.name))
        print r.data
        assert '<table class="permissions-table"' in r.data
        assert '<td>{0}'.format(self.u3.name) in r.data
        assert '<td>{0}'.format(self.u1.name) in r.data

    def test_copr_detail_doesnt_contain_forms_for_anonymous_user(self, f_users, f_coprs):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c3.name))
        assert '<form' not in r.data

    def test_copr_detail_allows_asking_for_permissions(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/permissions/'.format(self.u2.name, self.c2.name))
            # u1 is approved builder, check for that
            assert '/permissions_applier_change/' in r.data

    def test_copr_detail_doesnt_allow_owner_to_ask_for_permissions(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/permissions/'.format(self.u2.name, self.c2.name))
            assert '/permissions_applier_change/' not in r.data

    def test_detail_has_correct_permissions_form(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.get('/coprs/detail/{0}/{1}/permissions/'.format(self.u2.name, self.c3.name))

            assert r.data.count('nothing') == 2
            assert '<select id="copr_builder_1" name="copr_builder_1">' in r.data
            assert '<select id="copr_admin_1" name="copr_admin_1">' in r.data

    def test_copr_detail_doesnt_show_cancel_build_for_anonymous(self, f_users, f_coprs, f_builds):
        r = self.tc.get('/coprs/detail/{0}/{1}/'.format(self.u2.name, self.c2.name))
        assert '/cancel_build/' not in r.data

    def test_copr_detail_doesnt_allow_non_submitter_to_cancel_build(self, f_users, f_coprs, f_builds):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/builds/'.format(self.u2.name, self.c2.name))
            assert '/cancel_build/' not in r.data

    def test_copr_detail_allows_submitter_to_cancel_build(self, f_users, f_coprs, f_builds):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.get('/coprs/detail/{0}/{1}/builds/'.format(self.u2.name, self.c2.name))
            assert '/cancel_build/' in r.data


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


class TestCoprUpdate(CoprsTestCase):
    def test_update_no_changes(self, f_users, f_coprs, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.c1])
            r = c.post('/coprs/detail/{0}/{1}/update/'.format(self.u1.name, self.c1.name),
                       data = {'name': self.c1.name, 'fedora-18-x86_64': 'y', 'id': self.c1.id},
                       follow_redirects = True)
            assert 'Copr was updated successfully' in r.data

    def test_copr_admin_can_update(self, f_users, f_coprs, f_copr_permissions, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.post('/coprs/detail/{0}/{1}/update/'.format(self.u2.name, self.c3.name),
                       data = {'name': self.c3.name, 'fedora-rawhide-i386': 'y', 'id': self.c3.id},
                       follow_redirects = True)
            print r.data
            assert 'Copr was updated successfully' in r.data

    def test_update_multiple_chroots(self, f_users, f_coprs, f_copr_permissions, f_mock_chroots):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.c1, self.mc1, self.mc2, self.mc3])
            r = c.post('/coprs/detail/{0}/{1}/update/'.format(self.u1.name, self.c1.name),
                       data = {'name': self.c1.name, self.mc2.chroot_name: 'y', self.mc3.chroot_name: 'y', 'id': self.c1.id},
                       follow_redirects = True)
            assert 'Copr was updated successfully' in r.data
            self.db.session.add_all([self.c1, self.mc1, self.mc2, self.mc3])
            mock_chroots = self.models.MockChroot.query.join(self.models.CoprChroot).\
                                                        filter(self.models.CoprChroot.copr_id==\
                                                               self.c1.id).all()
            mock_chroots_names = map(lambda x: x.chroot_name, mock_chroots)
            assert self.mc2.chroot_name in mock_chroots_names
            assert self.mc3.chroot_name in mock_chroots_names
            assert self.mc1.chroot_name not in mock_chroots_names

    def test_update_deletes_multiple_chroots(self, f_users, f_coprs, f_copr_permissions, f_mock_chroots):
        # https://fedorahosted.org/copr/ticket/42
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2, self.mc1])
            # add one more mock_chroot, so that we can remove two
            cc = self.models.CoprChroot()
            cc.mock_chroot = self.mc1
            self.c2.copr_chroots.append(cc)

            r = c.post('/coprs/detail/{0}/{1}/update/'.format(self.u2.name, self.c2.name),
                       data = {'name': self.c2.name, self.mc1.chroot_name: 'y', 'id': self.c2.id},
                       follow_redirects = True)
            assert 'Copr was updated successfully' in r.data
            self.db.session.add_all([self.c2, self.mc1])
            mock_chroots = self.models.MockChroot.query.join(self.models.CoprChroot).\
                                                        filter(self.models.CoprChroot.copr_id==\
                                                               self.c2.id).all()
            assert len(mock_chroots) == 1

class TestCoprApplyForPermissions(CoprsTestCase):
    def test_apply(self, f_users, f_coprs):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u1, self.u2, self.c1])
            r = c.post('/coprs/detail/{0}/{1}/permissions_applier_change/'.format(self.u1.name, self.c1.name),
                       data = {'copr_builder': '1'},
                       follow_redirects = True)
            assert 'Successfuly updated' in r.data

            self.db.session.add_all([self.u1, self.u2, self.c1])
            new_perm = self.models.CoprPermission.query.filter(self.models.CoprPermission.user_id == self.u2.id).\
                                                        filter(self.models.CoprPermission.copr_id == self.c1.id).\
                                                        first()
            assert new_perm.copr_builder == 1
            assert new_perm.copr_admin == 0

    def test_apply_doesnt_lower_other_values_from_admin_to_request(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u1, self.u2, self.cp1, self.c2])
            r = c.post('/coprs/detail/{0}/{1}/permissions_applier_change/'.format(self.u2.name, self.c2.name),
                       data = {'copr_builder': 1, 'copr_admin': '1'},
                       follow_redirects = True)
            assert 'Successfuly updated' in r.data

            self.db.session.add_all([self.u1, self.c2])
            new_perm = self.models.CoprPermission.query.filter(self.models.CoprPermission.user_id == self.u1.id).\
                                                        filter(self.models.CoprPermission.copr_id == self.c2.id).\
                                                        first()
            assert new_perm.copr_builder == 2
            assert new_perm.copr_admin == 1

class TestCoprUpdatePermissions(CoprsTestCase):
    def test_cancel_permission(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c2])
            r = c.post('/coprs/detail/{0}/{1}/update_permissions/'.format(self.u2.name, self.c2.name),
                       data = {'copr_builder_1': '0'},
                       follow_redirects = True)

            # very volatile, but will fail fast if something changes
            check_string = '<select id="copr_builder_1" name="copr_builder_1"><option value="0">nothing</option><option value="1">'
            check_string += 'request</option><option selected value="2">approved</option></select>'
            assert check_string not in r.data

    def test_update_more_permissions(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u2.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.post('/coprs/detail/{0}/{1}/update_permissions/'.format(self.u2.name, self.c3.name),
                       data = {'copr_builder_1': '2', 'copr_admin_1': '1', 'copr_admin_3': '2'},
                       follow_redirects = True)
            self.db.session.add_all([self.c3, self.u1, self.u3])
            u1_c3_perms = self.models.CoprPermission.query.filter(self.models.CoprPermission.copr_id == self.c3.id).\
                                                           filter(self.models.CoprPermission.user_id == self.u1.id).\
                                                           first()
            assert u1_c3_perms.copr_builder == self.helpers.PermissionEnum.num('approved')
            assert u1_c3_perms.copr_admin == self.helpers.PermissionEnum.num('request')

            u3_c3_perms = self.models.CoprPermission.query.filter(self.models.CoprPermission.copr_id == self.c3.id).\
                                                           filter(self.models.CoprPermission.user_id == self.u3.id).\
                                                           first()
            assert u3_c3_perms.copr_builder == self.helpers.PermissionEnum.num('nothing')
            assert u3_c3_perms.copr_admin == self.helpers.PermissionEnum.num('approved')

    def test_copr_admin_can_update_permissions(self, f_users, f_coprs, f_copr_permissions):
        with self.tc as c:
            with c.session_transaction() as s:
                s['openid'] = self.u1.openid_name

            self.db.session.add_all([self.u2, self.c3])
            r = c.post('/coprs/detail/{0}/{1}/update_permissions/'.format(self.u2.name, self.c3.name),
                       data = {'copr_builder_1': '2', 'copr_admin_3': '2'},
                       follow_redirects = True)
            print r.data
            assert 'Copr permissions were updated' in r.data
