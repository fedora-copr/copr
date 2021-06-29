import datetime
import json
from unittest import mock

import flask
import pytest

from coprs import models, helpers, app
from copr_common.enums import ActionTypeEnum
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.complex_logic import (
    BuildConfigLogic,
    ComplexLogic,
    ProjectForking,
    ReposLogic,
)
from coprs.logic.coprs_logic import CoprChrootsLogic
from tests.coprs_test_case import (
    CoprsTestCase,
    new_app_context,
    TransactionDecorator,
)


class TestComplexLogic(CoprsTestCase):

    def test_fork_copr_sends_actions(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        with app.app_context():
            with mock.patch('flask.g') as mc_flask_g:
                mc_flask_g.user.name = self.u2.name
                fc1, created = ComplexLogic.fork_copr(self.c1, self.u2, u"dstname")
                self.db.session.commit()

                actions = ActionsLogic.get_many(ActionTypeEnum("fork")).all()
                assert len(actions) == 1
                data = json.loads(actions[0].data)
                assert data["user"] == self.u2.name
                assert data["copr"] == "dstname"
                assert data["builds_map"] == {'srpm-builds': {'bar': '00000005'},'fedora-18-x86_64': {'bar': '00000005-hello-world'}}

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_fork_prepare", "f_db")
    def test_fork_copr_projects_with_more_builds(self):
        flask.g.user = self.u2
        fc2, created = ComplexLogic.fork_copr(self.c2, self.u2, u"dstname")
        self.db.session.commit()
        actions = ActionsLogic.get_many(ActionTypeEnum("fork")).all()
        assert len(actions) == 1
        data = json.loads(actions[0].data)
        assert data["user"] == self.u2.name
        assert data["copr"] == "dstname"
        assert data["builds_map"] == {
            'srpm-builds': {'00000008-whatsupthere-world': '00000012', '00000006-hello-world': '00000013',
                            '00000010-new-package': '00000014', '00000011-new-package': '00000015'},
            'fedora-17-x86_64': {'8-whatsupthere-world': '00000012-whatsupthere-world',
                                 '6-hello-world': '00000013-hello-world',
                                 '10-new-package': '00000014-new-package'},
            'fedora-17-i386': {'8-whatsupthere-world': '00000012-whatsupthere-world',
                               '6-hello-world': '00000013-hello-world',
                               '11-new-package': '00000015-new-package'}}

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_fork_prepare", "f_db")
    def test_fork_copr_with_eoled_chroots(self):
        flask.g.user = self.u2

        # disable fedora-17-i386
        self.mc3.is_active = False
        self.db.session.add(self.mc3)
        self.db.session.commit()

        new_copr, created = ComplexLogic.fork_copr(self.c2, self.u2, u"dstname")
        assert created
        assert [cc.mock_chroot.name for cc in new_copr.copr_chroots] == [
            "fedora-17-x86_64"
        ]

        self.db.session.commit()
        actions = ActionsLogic.get_many(ActionTypeEnum("fork")).all()
        assert len(actions) == 1
        data = json.loads(actions[0].data)
        assert data["user"] == self.u2.name
        assert data["copr"] == "dstname"
        assert data["builds_map"] == {
            'srpm-builds': {
                '00000008-whatsupthere-world': '00000012',
                '00000006-hello-world': '00000013',
                '00000010-new-package': '00000014',
            },
            'fedora-17-x86_64': {
                '8-whatsupthere-world': '00000012-whatsupthere-world',
                '6-hello-world': '00000013-hello-world',
                '10-new-package': '00000014-new-package',
        }}

    def test_delete_expired_coprs(self, f_users, f_mock_chroots, f_coprs, f_builds, f_db):
        query = self.db.session.query(models.Copr)

        # nothing is deleted at the beginning
        assert len([c for c in query.all() if c.deleted]) == 0

        # one is to be deleted in the future
        self.c1.delete_after_days = 2
        # one is already to be deleted
        self.c2.delete_after = datetime.datetime.now() - datetime.timedelta(days=1)

        # and one is not to be temporary at all (c3)

        ComplexLogic.delete_expired_projects()
        self.db.session.commit()

        query = self.db.session.query(models.Copr)
        assert len(query.all()) == 3 # we only set deleted=true

        # some builds are not finished, nothing deleted yet
        assert len([c for c in query.all() if c.deleted]) == 0

        b = self.db.session.query(models.Build).get(3)
        b.canceled = True

        ComplexLogic.delete_expired_projects()
        self.db.session.commit()
        # some builds are not finished, nothing deleted yet
        assert len([c for c in query.all() if c.deleted]) == 1

        # test that build is deleted as well
        assert not self.db.session.query(models.Build).get(3)


class TestProjectForking(CoprsTestCase):

    def test_create_object(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        forking = ProjectForking(self.u1)
        o1 = FooModel(x=1, y=2, z=3)

        o2 = forking.create_object(FooModel, o1)
        assert o2.x == o1.x == 1
        assert o2.y == o1.y == 2
        assert o2.z == o1.z == 3

        o3 = forking.create_object(FooModel, o1, exclude=["z"])
        assert o3.x == o1.x == 1
        assert o3.y == o1.y == 2
        assert o3.z != o1.z
        assert not o3.z

    def test_fork_build(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        forking = ProjectForking(self.u1)
        fb1 = forking.fork_build(self.b1, self.c2, self.p2, self.b1.build_chroots)

        assert fb1.id != self.b1.id
        assert fb1.state == 'forked'
        assert len(self.b1.build_chroots) == len(fb1.build_chroots)

        ch, fch = self.b1.build_chroots[0], fb1.build_chroots[0]
        assert ch.build_id != fch.build_id
        assert ch.git_hash == fch.git_hash
        assert ch.started_on == fch.started_on
        assert ch.ended_on == fch.ended_on
        assert ch.mock_chroot_id == fch.mock_chroot_id

    @pytest.mark.usefixtures("f_copr_chroots_assigned_finished")
    def test_fork_check_assigned_copr_chroot(self):
        """
        When old build with old set of CoprChroots is forked, only the
        "still-enabled" copr_chroots get the new forked BuildChroot.
        """
        _side_effects = (self)
        assert len(self.c2.copr_chroots) == 2
        assert self.b1.copr != self.c2  # fork from different copr

        # enable f18-x86_64, that's where b1 was build into
        new_cch = CoprChrootsLogic.create_chroot(
            user=self.u1,
            copr=self.c2,
            mock_chroot=self.b1_bc[0].mock_chroot,
        )
        self.db.session.add(new_cch)

        forking = ProjectForking(self.u1)
        fork_b = forking.fork_build(self.b1, self.c2, self.p2,
                                    self.b1.build_chroots)

        # check the forked build_chroot has assigned copr_chroot
        assert len(new_cch.build_chroots) == 1
        assert fork_b.build_chroots == new_cch.build_chroots

    def test_fork_package(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        forking = ProjectForking(self.u1)
        fp1 = forking.fork_package(self.p1, self.c2)

        assert fp1.id != self.p1.id
        assert fp1.name == self.p1.name

    def test_fork_copr(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        with app.app_context():
            with mock.patch('flask.g') as mc_flask_g:
                mc_flask_g.user.name = self.u2.name
                forking = ProjectForking(self.u1)
                fc1 = forking.fork_copr(self.c1, "new-name")

                assert fc1.id != self.c1.id
                assert fc1.name == "new-name"
                assert fc1.forked_from_id == self.c1.id
                assert fc1.mock_chroots == self.c1.mock_chroots

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds", "f_db")
    def test_forking_into_existing_project(self):
        self.db.session.add_all([self.c1, self.c3, self.u1, self.u2])

        src_copr = self.c1
        src_user = self.u1
        dest_copr = self.c3
        dest_user = self.u2

        assert len(dest_copr.builds) == 0

        data = {
            "name": dest_copr.name,
            "ownername": dest_user.name,
            "source": "{0}/{1}".format(dest_user.name, dest_copr.name)
        }
        self.tc.post("/coprs/{0}/{1}/fork/".format(src_user.name, src_copr.name),
                     data=data)

        # No builds should be forked when confirm==False
        dest_copr = models.Copr.query.filter_by(id=dest_copr.id).one()
        assert len(dest_copr.builds) == 0

        data["confirm"] = "y"
        self.tc.post("/coprs/{0}/{1}/fork/".format(src_user.name, src_copr.name),
                     data=data)

        dest_copr = models.Copr.query.filter_by(id=dest_copr.id).one()
        assert len(dest_copr.builds) == 1

    def test_copr_by_repo_safe(self, f_users, f_coprs, f_mock_chroots, f_builds,
                               f_db):

        assert ComplexLogic.get_copr_by_repo_safe("xxx") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://a/b/c") == None

        assert ComplexLogic.get_copr_by_repo_safe("copr://user1/foocopr") != None

        # we could fix these in future
        assert ComplexLogic.get_copr_by_repo_safe("copr:///user1/foocopr") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://user1//foocopr") == None

    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_generate_build_config_with_dep_mistake(self):
        bcl = BuildConfigLogic
        main_repo = {
            "id": "copr_base",
            "name": "Copr repository",
            "baseurl": "http://copr-be-dev.cloud.fedoraproject.org"
                       "/results/user1/foocopr/fedora-18-x86_64/",
        }
        build_config = bcl.generate_build_config(self.c1, "fedora-18-x86_64")
        assert build_config["repos"] == [main_repo]

        self.c1.repos = "copr://non/existing"
        build_config = bcl.generate_build_config(self.c1, "fedora-18-x86_64")

        # We put the link there, even though baseurl points to 404.  The build
        # will later fail on downloading the repository and user will be
        # notified.
        assert len(build_config["repos"]) == 2
        assert build_config["repos"][1]["id"] == "copr_non_existing"

class FooModel(object):
    """
    Mocks SqlAlchemy db.Model
    """
    def __init__(self, x=None, y=None, z=None):
        self.x, self.y, self.z = x, y, z

    @property
    def __mapper__(self):
        return self

    @property
    def columns(self):
        return {"x": self.x, "y": self.y, "z": self.z}


class TestReposLogic(CoprsTestCase):
    @new_app_context
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_delete_reasons(self):
        """
        Make sure we correctly explain the reasons why and when chroots are
        going to be deleted.
        """
        # pylint: disable=protected-access

        # Make sure all chroots are active and not going to be deleted
        for chroot in self.c2.copr_chroots:
            assert chroot.is_active
            assert not chroot.delete_after_days

        # Check the reasoning when a project owner deleted the chroot
        chroot = self.c2.copr_chroots[0]
        CoprChrootsLogic.remove_copr_chroot(self.u2, chroot)
        assert chroot.delete_after_days == 6
        assert ReposLogic._delete_reason(self.c2.copr_chroots)\
            == ("The chroot x86_64 is disabled by a project owner and will "
                "remain available for another 6 days")

        # Check the reasoning when we marked the chroot as EOL
        chroot.mock_chroot.is_active = False
        chroot.delete_after = datetime.datetime.today() + datetime.timedelta(days=180)
        assert ReposLogic._delete_reason(self.c2.copr_chroots)\
            == ("The chroot x86_64 is EOL and will remain "
                "available for another 179 days")

        # Check the reasoning when we have multiple chroots with the same name
        # and release but each of its architectures was disabled for a different
        # reason
        assert self.c2.copr_chroots[0].mock_chroot.name_release\
            == self.c2.copr_chroots[1].mock_chroot.name_release

        chroot = self.c2.copr_chroots[1]
        CoprChrootsLogic.remove_copr_chroot(self.u2, chroot)
        assert ReposLogic._delete_reason(self.c2.copr_chroots)\
            == ("The chroot x86_64 is EOL and will remain "
                "available for another 179 days"
                "\n"
                "The chroot i386 is disabled by a project owner and will "
                "remain available for another 6 days")

        # Check the reasoning when multiple chroots are disabled for the same
        # reason
        chroot.mock_chroot.is_active = False
        chroot.delete_after = datetime.datetime.today() + datetime.timedelta(days=180)
        assert ReposLogic._delete_reason(self.c2.copr_chroots)\
            == ("The chroots x86_64 and i386 are EOL and will remain "
                "available for another 179 days")
