import json
from coprs import models
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprShowBuilds(CoprsTestCase):

    def test_copr_show_builds(self, f_users, f_coprs, f_mock_chroots,
                              f_builds, f_db):

        r = self.tc.get(
            "/coprs/{0}/{1}/builds/".format(self.u2.name, self.c2.name))
        assert r.data.count('<tr class="build-') == 2


class TestCoprAddBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_owner_can_add_build(self, f_users, f_coprs,
                                      f_mock_chroots, f_db):

        self.db.session.add_all([self.u1, self.c1])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u1.name, self.c1.name),
                              data={"pkgs": "http://testing.src.rpm"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_allowed_user_can_add_build(self, f_users, f_coprs,
                                             f_mock_chroots,
                                             f_copr_permissions, f_db):

        self.db.session.add_all([self.u2, self.c2])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c2.name),
                              data={"pkgs": "http://testing.src.rpm"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_not_yet_allowed_user_cant_add_build(self, f_users, f_coprs,
                                                      f_copr_permissions, f_db):

        self.db.session.add_all([self.u2, self.c3])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c3.name),
                              data={"pkgs": "http://testing.src.rpm"},
                              follow_redirects=True)

        assert not self.models.Build.query.first()

    @TransactionDecorator("u3")
    def test_copr_user_without_permission_cant_add_build(self, f_users,
                                                         f_coprs,
                                                         f_copr_permissions,
                                                         f_db):

        self.db.session.add_all([self.u1, self.c1])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u1.name, self.c1.name),
                              data={"pkgs": "http://testing.src.rpm"},
                              follow_redirects=True)

        assert not self.models.Build.query.first()


class TestCoprCancelBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_cancel_build(self, f_users, f_coprs,
                                                   f_mock_chroots,
                                                   f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.test_client.post("/coprs/{0}/{1}/cancel_build/{2}/"
                              .format(self.u1.name, self.c1.name, self.b1.id),
                              data={},
                              follow_redirects=True)

        assert self.models.Build.query.first().canceled is True

    @TransactionDecorator("u2")
    def test_copr_build_non_submitter_cannot_cancel_build(self, f_users,
                                                          f_coprs,
                                                          f_mock_chroots,
                                                          f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.test_client.post("/coprs/{0}/{1}/cancel_build/{2}/"
                              .format(self.u1.name, self.c1.name, self.b1.id),
                              data={},
                              follow_redirects=True)

        assert self.models.Build.query.first().canceled is False


class TestCoprDeleteBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_delete_build(self, f_users,
                                                   f_coprs, f_mock_chroots,
                                                   f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        pkgs = "one two three"
        self.b1.pkgs = pkgs
        r = self.test_client.post(
            "/coprs/{0}/{1}/delete_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)
        assert "Build was deleted" in r.data
        b = (self.models.Build.query.filter(
            self.models.Build.id == self.b1.id)
            .first())
        assert b is None
        act = self.models.Action.query.first()
        assert act.object_type == "build-succeeded"
        assert act.old_value == "user1/foocopr"
        assert json.loads(act.data)["pkgs"] == pkgs

    @TransactionDecorator("u2")
    def test_copr_build_non_submitter_cannot_delete_build(self, f_users,
                                                          f_coprs,
                                                          f_mock_chroots,
                                                          f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        r = self.test_client.post(
            "/coprs/{0}/{1}/delete_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)

        assert "allowed to delete this build" in r.data
        b = (self.models.Build.query.filter(
            self.models.Build.id == self.b1.id)
            .first())

        assert b is not None


class TestCoprRepeatBuild(CoprsTestCase):
    @TransactionDecorator("u1")
    def test_copr_build_chroots_subset_preserved_on_build_repeat(
            self, f_users, f_coprs, f_mock_chroots_many, f_db):
        self.b_few_chroots = models.Build(
            id=2345,
            copr=self.c1, user=self.u1,
            submitted_on=50, started_on=139086644000,
            pkgs="http://example.com/copr-keygen-1.58-1.fc20.src.rpm",
            pkg_version="1.58"
        )

        self.db.session.add(self.b_few_chroots)
        self.status_by_chroot = {
            'epel-5-i386': 0,
            'fedora-20-i386': 1,
            'fedora-20-x86_64': 1,
            'fedora-21-i386': 1,
            'fedora-21-x86_64': 4
        }

        for chroot in self.b_few_chroots.copr.active_chroots:
            if chroot.name in self.status_by_chroot:
                buildchroot = models.BuildChroot(
                    build=self.b_few_chroots,
                    mock_chroot=chroot,
                    status = self.status_by_chroot[chroot.name])
                self.db.session.add(buildchroot)

        self.db.session.add_all([self.u1, self.c1, self.b_few_chroots])
        self.db.session.commit()

        r = self.test_client.post(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b_few_chroots.id),
            data={},
            follow_redirects=True)

        assert "Build was resubmitted" in r.data

        new_build = self.models.Build.query.filter(
            self.models.Build.id != 2345).first()

        expected_build_chroots_name_set = set(self.status_by_chroot.keys())
        result_build_chroots_name_set = set([c.name for c in new_build.chroots])

        assert result_build_chroots_name_set == expected_build_chroots_name_set


    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_repeat_build(self, f_users,
                                                   f_coprs, f_mock_chroots,
                                                   f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        pkgs = "one two three"
        self.b1.pkgs = pkgs
        self.db.session.commit()

        r = self.test_client.post(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)

        assert "Build was resubmitted" in r.data
        assert len(self.models.Build.query
                   .filter(self.models.Build.pkgs == pkgs)
                   .all()) == 2

    @TransactionDecorator("u2")
    def test_copr_build_non_submitter_cannot_repeat_build(self, f_users,
                                                          f_coprs,
                                                          f_mock_chroots,
                                                          f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1, self.b1])
        r = self.test_client.post(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)

        assert "t have permissions to build" in r.data
