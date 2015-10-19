import json
from coprs import models
from coprs.helpers import StatusEnum
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprShowBuilds(CoprsTestCase):

    def test_copr_show_builds(self, f_users, f_coprs, f_mock_chroots,
                              f_builds, f_db):

        r = self.tc.get(
            "/coprs/{0}/{1}/builds/".format(self.u2.name, self.c2.name))
        assert r.data.count(b'<tr class="build-') == 2


class TestCoprAddBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_owner_can_add_build(self, f_users, f_coprs,
                                      f_mock_chroots, f_db):

        self.db.session.add_all([self.u1, self.c1])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u1.name, self.c1.name),
                              data={"pkgs": "http://example.com/testing.src.rpm"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://example.com/testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_allowed_user_can_add_build(self, f_users, f_coprs,
                                             f_mock_chroots,
                                             f_copr_permissions, f_db):

        self.db.session.add_all([self.u2, self.c2])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c2.name),
                              data={"pkgs": "http://example.com/testing.src.rpm"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://example.com/testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_not_yet_allowed_user_cant_add_build(self, f_users, f_coprs,
                                                      f_copr_permissions, f_db):

        self.db.session.add_all([self.u2, self.c3])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c3.name),
                              data={"pkgs": "http://example.com/testing.src.rpm"},
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
                              data={"pkgs": "http://example.com/testing.src.rpm"},
                              follow_redirects=True)

        assert not self.models.Build.query.first()

    @TransactionDecorator("u1")
    def test_copr_default_options(self, f_users, f_mock_chroots, f_db):
        self.test_client.post(
            "/coprs/{0}/new/".format(self.u1.name),
            data={"name": "foo",
                  "fedora-rawhide-i386": "y",  # Needed?
                  "arches": ["i386"],  # Needed?
                  "build_enable_net": None,
                  },
            follow_redirects=True)

        r = self.tc.get(
            "/coprs/{0}/{1}/add_build/".format(self.u1.name, "foo"))
        assert b'<input checked id="enable_net" name="enable_net"' not in r.data


class TestCoprCancelBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_cancel_build(self, f_users, f_coprs,
                                                   f_mock_chroots,
                                                   f_builds, f_db):

        for bc in self.b1_bc:
            bc.status = StatusEnum("pending")
            bc.ended_on = None
        self.db.session.add_all(self.b1_bc)
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
        for bc in self.b1_bc:
            bc.status = StatusEnum("pending")
            bc.ended_on = None
        self.db.session.add_all(self.b1_bc)
        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.test_client.post("/coprs/{0}/{1}/cancel_build/{2}/"
                              .format(self.u1.name, self.c1.name, self.b1.id),
                              data={},
                              follow_redirects=True)

        assert self.models.Build.query.first().canceled is False


class TestCoprDeleteBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_delete_build_old(self, f_users,
                                                   f_coprs, f_mock_chroots,
                                                   f_builds):

        pkgs = "http://example.com/one.src.rpm"
        self.b1.pkgs = pkgs
        for bc in self.b1_bc:
            bc.git_hash = None
        self.db.session.add_all(self.b1_bc)
        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.db.session.commit()

        r = self.test_client.post(
            "/coprs/{0}/{1}/delete_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)
        assert b"Build has been deleted" in r.data
        b = (self.models.Build.query.filter(
            self.models.Build.id == self.b1.id)
            .first())
        assert b is None
        act = self.models.Action.query.first()
        assert act.object_type == "build"
        assert act.old_value == "user1/foocopr"
        assert json.loads(act.data)["src_pkg_name"] == self.b1.src_pkg_name

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_delete_build(self, f_users,
                                                   f_coprs, f_mock_chroots,
                                                   f_builds):
        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.db.session.commit()
        expected_dir = self.b1.result_dir_name
        b_id = self.b1.id
        url = "/coprs/{0}/{1}/delete_build/{2}/".format(self.u1.name, self.c1.name, b_id)

        r = self.test_client.post(
            url, data={}, follow_redirects=True)
        assert r.status_code == 200

        b = (
            self.models.Build.query
            .filter(self.models.Build.id == b_id)
            .first()
        )
        assert b is None
        act = self.models.Action.query.first()
        assert act.object_type == "build"
        assert act.old_value == "user1/foocopr"
        assert json.loads(act.data)["result_dir_name"] == expected_dir

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
        assert b"not allowed to delete build" in r.data
        b = (self.models.Build.query.filter(
            self.models.Build.id == self.b1.id)
            .first())

        assert b is not None


class TestCoprRepeatBuild(CoprsTestCase):
    @TransactionDecorator("u1")
    def test_copr_build_basic_build_repeat(
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
                    status=self.status_by_chroot[chroot.name])
                self.db.session.add(buildchroot)

        self.db.session.add_all([self.u1, self.c1, self.b_few_chroots])
        self.db.session.commit()

        r = self.test_client.post(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b_few_chroots.id),
            data={},
            follow_redirects=True)

        assert r.status_code == 200
        # no longer using URL
        #assert self.b_few_chroots.pkgs in r.data
        assert "Resubmit build {}".format(self.b_few_chroots.id).encode("utf-8") in r.data

        # TODO: maybe test, that only failed chroots are selected

        # new_build = self.models.Build.query.filter(
        #     self.models.Build.id != 2345).first()
        #
        # expected_build_chroots_name_set = set(self.status_by_chroot.keys())
        # result_build_chroots_name_set = set([c.name for c in new_build.chroots])
        #
        # assert result_build_chroots_name_set == expected_build_chroots_name_set

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

        assert "Resubmit build {}".format(self.b1.id).encode("utf-8") in r.data
        assert r.status_code == 200
        # assert "Build was resubmitted" in r.data
        # assert len(self.models.Build.query
        #            .filter(self.models.Build.pkgs == pkgs)
        #            .all()) == 2

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

        # import ipdb; ipdb.set_trace()
        assert b"You are not allowed to repeat this build." in r.data

    @TransactionDecorator("u1")
    def test_copr_build_package_urls(self, f_users,
                                     f_coprs,
                                     f_mock_chroots,
                                     f_builds, f_db):

        self.db.session.add_all([self.u1, self.c1])

        urls = [
            "http://example.com/foo.src.rpm",
            "foo://example.com/foo.src.rpm",
            "http://example.com/foo",
        ]
        r = []
        route = "/coprs/{0}/{1}/new_build/".format(self.u1.name, self.c1.name)
        for i, url in enumerate(urls):
            r.insert(i, self.test_client.post(route, data={"pkgs": url}, follow_redirects=True))

        assert b"New build has been created" in r[0].data
        assert b"doesn&#39;t seem to be a valid URL" in r[1].data
        assert b"doesn&#39;t seem to be a valid SRPM URL" in r[2].data
