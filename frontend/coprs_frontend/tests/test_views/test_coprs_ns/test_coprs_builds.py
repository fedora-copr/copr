import json
import pytest
from lxml import html

from copr_common.enums import StatusEnum, BuildSourceEnum
from coprs import models
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestCoprShowBuilds(CoprsTestCase):

    def test_copr_show_builds(self, f_users, f_coprs, f_mock_chroots,
                              f_builds, f_db):

        r = self.tc.get(
            "/coprs/{0}/{1}/builds/".format(self.u2.name, self.c2.name))
        assert r.data.count(b'<tr class="build-') == 2


class TestCoprAddBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_user_can_add_build(self, f_users, f_coprs,
                                      f_mock_chroots, f_db):

        self.db.session.add_all([self.u1, self.c1])
        x = self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u1.name, self.c1.name),
                              data={"pkgs": "http://example.com/testing.src.rpm", "source_type": "link"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://example.com/testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_allowed_user_can_add_build(self, f_users, f_coprs,
                                             f_mock_chroots,
                                             f_copr_permissions, f_db):

        self.db.session.add_all([self.u2, self.c2])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c2.name),
                              data={"pkgs": "http://example.com/testing.src.rpm", "source_type": "link"},
                              follow_redirects=True)

        assert self.models.Build.query.first().pkgs == "http://example.com/testing.src.rpm"

    @TransactionDecorator("u1")
    def test_copr_not_yet_allowed_user_cant_add_build(self, f_users, f_coprs,
                                                      f_copr_permissions, f_db):

        self.u1.admin = False
        self.db.session.add_all([self.u1, self.u2, self.c3])

        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u2.name, self.c3.name),
                              data={"pkgs": "http://example.com/testing.src.rpm"},
                              follow_redirects=True)

        assert not self.models.Build.query.first()

    @TransactionDecorator("u2")
    def test_copr_user_cant_add_build_to_admin_project(self, f_users, f_coprs,
                                                       f_copr_permissions, f_db):
        """ test for issue#970 """
        self.db.session.add_all([self.u1, self.c1])
        self.test_client.post("/coprs/{0}/{1}/new_build/"
                              .format(self.u1.name, self.c1.name),
                              data={"pkgs": "http://example.com/testing.src.rpm"},
                              follow_redirects=True)
        assert not self.models.Build.query.first()


    @TransactionDecorator("u3")
    def test_copr_user_without_permission_cant_add_build(self, f_users,
                                                         f_coprs,
                                                         f_copr_permissions,
                                                         f_db):
        self.u1.admin = False
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
        self.u1.admin = False
        self.db.session.add_all(self.b1_bc)
        self.db.session.add_all([self.u1, self.c1, self.b1])
        self.test_client.post("/coprs/{0}/{1}/cancel_build/{2}/"
                              .format(self.u1.name, self.c1.name, self.b1.id),
                              data={},
                              follow_redirects=True)

        assert self.models.Build.query.first().canceled is False


class TestCoprDeleteBuild(CoprsTestCase):

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_delete_build_old(self, f_users, f_coprs, f_build_few_chroots, f_db):
        self.db.session.add_all([self.u1, self.c1, self.b_few_chroots])
        self.b_few_chroots.build_chroots[1].status= StatusEnum("canceled")
        self.db.session.commit()

        expected_chroot_builddirs = {'srpm-builds': [self.b_few_chroots.result_dir]}
        self.b_few_chroots.copr.appstream = True
        for chroot in self.b_few_chroots.build_chroots:
            expected_chroot_builddirs[chroot.name] = [chroot.result_dir]

        expected_dir = self.b_few_chroots.result_dir
        r = self.test_client.post(
            "/coprs/{0}/{1}/delete_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b_few_chroots.id),
            data={}, follow_redirects=True)

        assert b"Build has been deleted" in r.data
        b = (self.models.Build.query.filter(
            self.models.Build.id == self.b_few_chroots.id).first())
        assert b is None

        act = self.models.Action.query.first()
        data = json.loads(act.data)
        assert act.object_type == "build"
        assert data.get('ownername') == "user1"
        assert data.get('projectname') == "foocopr"
        assert json.loads(act.data)["chroot_builddirs"] == expected_chroot_builddirs

    @TransactionDecorator("u1")
    def test_copr_build_submitter_can_delete_build(self, f_users,
                                                   f_coprs, f_mock_chroots,
                                                   f_builds):
        self.db.session.add(self.b1)
        self.db.session.commit()

        b_id = self.b1.id
        self.b1.copr.appstream = True
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
        data = json.loads(act.data)
        assert act.object_type == "build"
        assert data.get('ownername') == "user1"
        assert data.get('projectname') == "foocopr"

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

    @TransactionDecorator("u1")
    def test_copr_delete_multiple_builds_sends_single_action(self, f_users,
                                                             f_coprs,
                                                             f_pr_build):
        for bc in self.b2_bc:
            bc.status = StatusEnum("canceled")
        self.db.session.add_all(self.b2_bc)
        self.db.session.add_all([self.b1, self.b2])
        self.db.session.commit()

        b_id1 = self.b1.id
        b_id2 = self.b2.id
        b_id3 = self.b_pr.id
        url = "/coprs/{0}/{1}/delete_builds/".format(self.u1.name, self.c1.name)

        r = self.test_client.post(
            url, data={"build_ids[]": [b_id1, b_id2, b_id3]}, follow_redirects=True)
        assert r.status_code == 200

        b1 = (
            self.models.Build.query
            .filter(self.models.Build.id == b_id1)
            .first()
        )
        b2 = (
            self.models.Build.query
            .filter(self.models.Build.id == b_id2)
            .first()
        )

        assert b1 is None
        assert b2 is None

        act = self.models.Action.query.first()
        data = json.loads(act.data)
        assert act.object_type == "builds"
        assert data.get('ownername') == "user1"
        assert data.get('projectname') == "foocopr"
        assert data.get('project_dirnames') == {
            'foocopr': {
                # they'd usually look like ID-PKGNAME, not 'bar'
                'fedora-18-x86_64': ['bar', 'bar'],
                'srpm-builds': ['bar', '00000002']},
            'foocopr:PR': {
                'fedora-17-x86_64': ['0000PR-pr-package'],
                'srpm-builds': ['0000PR'],
            }
        }

    @TransactionDecorator("u1")
    def test_copr_delete_package_sends_single_action(self, f_users,
                                                     f_coprs, f_mock_chroots,
                                                     f_builds):
        for bc in self.b2_bc:
            bc.status = StatusEnum("canceled")
        self.db.session.add_all(self.b2_bc)
        self.db.session.add_all([self.b1, self.b2, self.p1])
        self.db.session.commit()

        b_id1 = self.b1.id
        b_id2 = self.b2.id
        p_id = self.p1.id
        url = "/coprs/{0}/{1}/package/{2}/delete".format(self.u1.name, self.c1.name, p_id)

        r = self.test_client.post(
            url, data={}, follow_redirects=True)
        assert r.status_code == 200

        b1 = (
            self.models.Build.query
            .filter(self.models.Build.id == b_id1)
            .first()
        )
        b2 = (
            self.models.Build.query
            .filter(self.models.Build.id == b_id2)
            .first()
        )

        assert b1 is None
        assert b2 is None

        act = self.models.Action.query.first()
        data = json.loads(act.data)
        assert act.object_type == "builds"
        assert data.get('ownername') == "user1"
        assert data.get('projectname') == "foocopr"


class TestCoprRepeatBuild(CoprsTestCase):
    @TransactionDecorator("u1")
    def test_copr_build_basic_build_repeat(
            self, f_users, f_coprs, f_mock_chroots_many, f_db):
        self.b_few_chroots = models.Build(
            id=2345,
            copr=self.c1,
            copr_dir=self.c1_dir,
            user=self.u1,
            submitted_on=50,
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
        self.u1.admin = False
        self.db.session.add_all([self.u1, self.c1, self.b1])
        r = self.test_client.post(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u1.name, self.c1.name, self.b1.id),
            data={},
            follow_redirects=True)

        assert b"You are not allowed to repeat this build." in r.data

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_rebuild_srpm_upload_generates_chroots(self):
        """
        Resubmitting SRPM-uploaded build is a special case because it skips the
        import phase and goes directly to building RPMs.

        We encountered an issue, that resubmitting a successfully built lead to
        infinitely waiting state. This tests makes sure it doesn't happen
        anymore. Please see RHBZ 1906062 for more information.
        """
        b1 = self.models.Build.query.filter(self.models.Build.id == 1).one()
        b1.srpm_url = "http://foo.bar/baz.src.rpm"
        b1.source_type = BuildSourceEnum("upload")
        b1.pkgs = "baz"
        for chroot in b1.build_chroots:
            chroot.status = StatusEnum("succeeded")

        self.db.session.add_all([self.u1, self.c1, b1])
        self.db.session.commit()

        r = self.test_client.post(
            "/coprs/{0}/{1}/new_build_rebuild/{2}/"
            .format(self.u1.name, self.c1.name, b1.id),
            data={"fedora-18-x86_64": ""},
            follow_redirects=True)
        assert r.status_code == 200

        builds = (self.models.Build.query
                  .filter(self.models.Build.pkgs == "baz")
                  .all())
        assert len(builds) == 2
        assert builds[-1].srpm_url == builds[0].srpm_url
        assert builds[-1].chroots == builds[0].chroots
        assert len(builds[-1].build_chroots) == len(builds[0].build_chroots)

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
            r.insert(i, self.test_client.post(route, data={"pkgs": url, "source_type": "link"}, follow_redirects=True))

        assert b"doesn&#39;t seem to be a valid URL" not in r[0].data
        assert b"doesn&#39;t seem to be a valid URL" not in r[0].data
        assert b"doesn&#39;t seem to be a valid URL" in r[1].data
        assert b"doesn&#39;t seem to be a valid URL" in r[2].data

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots",
                             "f_builds", "f_db")
    def test_copr_repeat_build_available_chroots(self):
        """
        When resubmitting a build, make sure that previously failed chroots
        are now checked-on by default while previously succeeded chroots are
        unchecked by default.
        """
        self.db.session.add_all([self.u2, self.c2, self.b3] + self.b3_bc)

        # Make sure our build chroots are sorted, so we can easily compare it
        # with what is rendered in the web UI (they are sorted there)
        self.b3_bc.sort(key=lambda x: x.name)

        self.b3_bc[0].status = StatusEnum("failed")
        self.b3_bc[1].status = StatusEnum("succeeded")
        self.db.session.add_all(self.b3_bc)

        response = self.test_client.get(
            "/coprs/{0}/{1}/repeat_build/{2}/"
            .format(self.u2.name, self.c2.name, self.b3.id),
            data={},
            follow_redirects=True)
        assert response.status_code == 200

        tree = html.fromstring(response.data)
        inputs = tree.xpath("//input[@name='chroots']")
        assert len(inputs) == 2

        assert inputs[0].get("value")== self.b3_bc[0].name
        assert inputs[0].checked

        assert inputs[1].get("value")== self.b3_bc[1].name
        assert not inputs[1].checked
