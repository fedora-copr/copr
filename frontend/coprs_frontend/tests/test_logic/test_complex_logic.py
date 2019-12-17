import datetime
import json
from unittest import mock

from coprs import models, helpers, app
from copr_common.enums import ActionTypeEnum
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.complex_logic import ComplexLogic, ProjectForking
from tests.coprs_test_case import CoprsTestCase, new_app_context


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
    @mock.patch("flask.g")
    def test_fork_copr_projects_with_more_builds(self, mc_flask_g, f_users, f_fork_prepare, f_db):
        mc_flask_g.user.name = self.u2.name
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

    def test_copr_by_repo_safe(self, f_users, f_coprs, f_mock_chroots, f_builds,
                               f_db):

        assert ComplexLogic.get_copr_by_repo_safe("xxx") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://a/b/c") == None

        assert ComplexLogic.get_copr_by_repo_safe("copr://user1/foocopr") != None

        # we could fix these in future
        assert ComplexLogic.get_copr_by_repo_safe("copr:///user1/foocopr") == None
        assert ComplexLogic.get_copr_by_repo_safe("copr://user1//foocopr") == None


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
