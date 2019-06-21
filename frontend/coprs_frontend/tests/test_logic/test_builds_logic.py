# -*- encoding: utf-8 -*-
import json

import pytest
import time

from sqlalchemy.orm.exc import NoResultFound
from coprs import models
from coprs.constants import MAX_BUILD_TIMEOUT

from copr_common.enums import StatusEnum
from coprs.exceptions import ActionInProgressException, InsufficientRightsException, MalformedArgumentException
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.builds_logic import BuildsLogic

from tests.coprs_test_case import CoprsTestCase


class TestBuildsLogic(CoprsTestCase):
    data = """
{
  "builds":[
    {
      "id": 5,
      "task_id": 5,
      "srpm_url": "http://foo",
      "status": 1,
      "pkg_name": "foo",
      "pkg_version": 1
    }
  ]
}"""

    def test_add_only_adds_active_chroots(self, f_users, f_coprs, f_builds,
                                          f_mock_chroots, f_db):

        self.mc2.is_active = False
        self.db.session.commit()
        b = BuildsLogic.add(self.u2, "blah", self.c2)
        self.db.session.commit()
        build_id = b.id
        expected_name = self.mc3.name
        assert len(b.chroots) == 0

        self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data)

        b = BuildsLogic.get(build_id).first()
        assert len(b.chroots) == 1
        assert b.chroots[0].name == expected_name

    def test_add_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs,
                                                       f_actions, f_db):

        with pytest.raises(ActionInProgressException):
            b = BuildsLogic.add(self.u1, "blah", self.c1)
        self.db.session.rollback()

    def test_add_assigns_params_correctly(self, f_users, f_coprs,
                                          f_mock_chroots, f_db):

        params = dict(
            user=self.u1,
            pkgs="blah",
            copr=self.c1,
            repos="repos",
            timeout=5000)

        b = BuildsLogic.add(**params)
        for k, v in params.items():
            assert getattr(b, k) == v

    def test_add_error_on_multiply_src(self, f_users, f_coprs,
                                          f_mock_chroots, f_db):

        params = dict(
            user=self.u1,
            pkgs="blah blah",
            copr=self.c1,
            repos="repos",
            timeout=5000)

        with pytest.raises(MalformedArgumentException):
            BuildsLogic.add(**params)

    """get_monitor_data output changed
    def test_monitor_logic(self, f_users, f_coprs, f_builds, f_mock_chroots_many, f_build_few_chroots, f_db):
        copr = self.c1
        md = BuildsMonitorLogic.get_monitor_data(copr)
        assert len(md) == 1
        assert len(md[0]["build_chroots"]) == 15
    """

    def test_build_queue_1(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_importing_queue().all()
        assert len(data) == 2

    def test_build_queue_2(self, f_users, f_coprs, f_mock_chroots, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_importing_queue().all()
        assert len(data) == 0

    def test_build_queue_3(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b1_bc, self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 0
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 0

    def test_build_queue_4(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        time_now = int(time.time())
        for build_chroots in [self.b1_bc, self.b2_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = StatusEnum("running")
                build_chroot.started_on = time_now - 2 * MAX_BUILD_TIMEOUT
                build_chroot.ended_on = None
        for build_chroots in [self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = StatusEnum("failed")
                build_chroot.started_on = time_now - 2 * MAX_BUILD_TIMEOUT
                build_chroot.ended_on = None

        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()

        assert len(data) == 2
        assert set([data[0], data[1]]) == set([self.b1_bc[0], self.b2_bc[0]])

    def test_build_queue_5(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 4 # pending
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 5

    def test_build_queue_6(self, f_users, f_coprs, f_mock_chroots, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 0

    def test_delete_build_exceptions(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for bc in self.b4_bc:
            bc.status = StatusEnum("succeeded")
            bc.ended_on = time.time()
        self.u1.admin = False

        self.db.session.add_all(self.b4_bc)
        self.db.session.add(self.b4)
        self.db.session.add(self.u1)
        self.db.session.commit()
        with pytest.raises(InsufficientRightsException):
            BuildsLogic.delete_build(self.u1, self.b4)

        self.b1_bc[0].status = StatusEnum("running")
        self.db.session.add(self.b1_bc[0])
        self.db.session.commit()
        with pytest.raises(ActionInProgressException):
            BuildsLogic.delete_build(self.u1, self.b1)

        self.copr_persistent = models.Copr(name=u"persistent_copr", user=self.u2, persistent=True)
        self.copr_dir = models.CoprDir(name="persistent_copr", main=True, copr=self.copr_persistent)
        self.build_persistent = models.Build(
            copr=self.copr_persistent, copr_dir=self.copr_dir,
            package=self.p2, user=self.u2, submitted_on=100)
        with pytest.raises(InsufficientRightsException):
            BuildsLogic.delete_build(self.u2, self.build_persistent)


    def test_delete_build_as_admin(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b4.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b4.result_dir
        for bc in self.b4_bc:
            bc.status = StatusEnum("succeeded")
            bc.ended_on = time.time()

        self.u1.admin = True

        self.db.session.add_all(self.b4_bc)
        self.db.session.add(self.b4)
        self.db.session.add(self.u1)
        self.db.session.commit()

        expected_chroots_to_delete = set()
        for bchroot in self.b4_bc:
            expected_chroots_to_delete.add(bchroot.name)

        assert len(ActionsLogic.get_many().all()) == 0
        BuildsLogic.delete_build(self.u1, self.b4)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b4.id).one()

    def test_delete_build_basic(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b1.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b1.result_dir
        self.db.session.add(self.b1)
        self.db.session.commit()

        expected_chroots_to_delete = set()
        for bchroot in self.b1_bc:
            expected_chroots_to_delete.add(bchroot.name)

        assert len(ActionsLogic.get_many().all()) == 0
        BuildsLogic.delete_build(self.u1, self.b1)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()
        delete_data = json.loads(action.data)
        assert delete_data['chroot_builddirs'] == {'srpm-builds': 'bar', 'fedora-18-x86_64': 'bar'}

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b1.id).one()

    def test_mark_as_failed(self, f_users, f_coprs, f_mock_chroots, f_builds):
        self.b1.source_status = StatusEnum("succeeded")
        self.db.session.commit()
        BuildsLogic.mark_as_failed(self.b1.id)
        BuildsLogic.mark_as_failed(self.b3.id)

        assert self.b1.status == StatusEnum("succeeded")
        assert self.b3.status == StatusEnum("failed")
        assert type(BuildsLogic.mark_as_failed(self.b3.id)) == models.Build

    def test_build_garbage_collector_works(self, f_users, f_coprs,
            f_mock_chroots, f_builds, f_db):

        assert len(self.db.session.query(models.Build).all()) == 4

        p = models.Package.query.filter_by(name='whatsupthere-world').first()
        p.max_builds = 1
        self.db.session.add(p)

        assert len(models.Package.query.all()) == 3
        BuildsLogic.clean_old_builds()

        # we can not delete not-yet finished builds!
        assert len(self.db.session.query(models.Build).all()) == 4

        for bch in self.b3.build_chroots:
            bch.status = StatusEnum('succeeded')
            self.db.session.add(bch)

        assert len(self.db.session.query(models.Build).all()) == 4
        BuildsLogic.clean_old_builds()
        assert len(self.db.session.query(models.Build).all()) == 3
