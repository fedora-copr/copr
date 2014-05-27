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
        assert act.object_type == "build"
        assert act.old_value == "user1/foocopr"
        assert act.data == pkgs

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
