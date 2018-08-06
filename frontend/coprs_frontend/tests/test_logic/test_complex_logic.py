import json
from unittest import mock

from coprs.helpers import ActionTypeEnum
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.complex_logic import ComplexLogic, ProjectForking
from tests.coprs_test_case import CoprsTestCase


class TestComplexLogic(CoprsTestCase):

    @mock.patch("flask.g")
    def test_fork_copr_sends_actions(self, mc_flask_g, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        mc_flask_g.user.name = self.u2.name
        fc1, created = ComplexLogic.fork_copr(self.c1, self.u2, u"dstname")
        self.db.session.commit()

        actions = ActionsLogic.get_many(ActionTypeEnum("fork")).all()
        assert len(actions) == 1
        data = json.loads(actions[0].data)
        assert data["user"] == self.u2.name
        assert data["copr"] == "dstname"
        assert data["builds_map"] == {'fedora-18-x86_64': ['bar', '00000005-hello-world'], 'srpm-builds': ['bar', '00000005']}



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
        fb1 = forking.fork_build(self.b1, self.c2, self.p2)

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

    @mock.patch("flask.g")
    def test_fork_copr(self, mc_flask_g, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        mc_flask_g.user.name = self.u2.name
        forking = ProjectForking(self.u1)
        fc1 = forking.fork_copr(self.c1, "new-name")

        assert fc1.id != self.c1.id
        assert fc1.name == "new-name"
        assert fc1.forked_from_id == self.c1.id
        assert fc1.mock_chroots == self.c1.mock_chroots


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
