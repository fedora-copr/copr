# -*- encoding: utf-8 -*-

import pytest
import time
from coprs import helpers

from coprs.exceptions import ActionInProgressException
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.builds_logic import BuildsMonitorLogic

from tests.coprs_test_case import CoprsTestCase


class TestBuildsLogic(CoprsTestCase):

    def test_add_only_adds_active_chroots(self, f_users, f_coprs, f_builds,
                                          f_mock_chroots, f_db):

        self.mc2.is_active = False
        self.db.session.commit()
        b = BuildsLogic.add(self.u2, "blah blah", self.c2)
        self.db.session.commit()
        assert b.chroots[0].name == self.mc3.name

    def test_add_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs,
                                                       f_actions, f_db):

        with pytest.raises(ActionInProgressException):
            b = BuildsLogic.add(self.u1, "blah blah", self.c1)
        self.db.session.rollback()

    def test_add_assigns_params_correctly(self, f_users, f_coprs,
                                          f_mock_chroots, f_db):

        params = dict(
            user=self.u1,
            pkgs="blah blah",
            copr=self.c1,
            repos="repos",
            memory_reqs=3000,
            timeout=5000)

        b = BuildsLogic.add(**params)
        for k, v in params.items():
            assert getattr(b, k) == v

    def test_monitor_logic(self, f_users, f_coprs, f_mock_chroots_many, f_build_many_chroots, f_db):
        copr = self.c1
        md = BuildsMonitorLogic.get_monitor_data(copr)
        results = md["packages"][-1][2]
        mchroots = md["chroots"]

        for chr, res in zip(mchroots, results):
            assert helpers.StatusEnum(self.status_by_chroot[chr]) == res[1]

    def test_build_queue_1(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_task_queue().all()
        assert len(data) == 5

    def test_build_queue_2(self, f_users, f_coprs, f_mock_chroots, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_task_queue().all()
        assert len(data) == 0

    def test_build_queue_3(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b1_bc, self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 0
        self.db.session.commit()
        data = BuildsLogic.get_build_task_queue().all()
        assert len(data) == 0

    def test_build_queue_4(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b1_bc, self.b2_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 3  # running
        for build_chroots in [self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 0

        time_now = int(time.time())

        self.b1.started_on = time_now - 100000

        self.db.session.commit()
        data = BuildsLogic.get_build_task_queue().all()

        assert len(data) == 1
        assert data[0] == self.b1_bc[0]
