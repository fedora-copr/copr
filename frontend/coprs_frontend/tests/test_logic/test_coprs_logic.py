import json
import pytest

from datetime import datetime, timedelta, date
from flask_whooshee import Whooshee

from sqlalchemy import desc
from unittest import mock

from copr_common.enums import ActionTypeEnum, StatusEnum
from coprs import app
from coprs.forms import PinnedCoprsForm, ChrootForm, ModuleEnableNameValidator
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic, PinnedCoprsLogic
from coprs.logic.users_logic import UsersLogic
from coprs.logic.complex_logic import ComplexLogic

from coprs import models
from coprs.whoosheers import CoprWhoosheer
from tests.coprs_test_case import CoprsTestCase, new_app_context
from coprs.exceptions import (
    ConflictingRequest,
    InsufficientRightsException,
)


class TestCoprsLogic(CoprsTestCase):

    def test_legal_flag_doesnt_block_copr_functionality(self, f_users,
                                                        f_coprs, f_db):
        self.db.session.add(self.models.Action(
            object_type="copr",
            object_id=self.c1.id,
            action_type=ActionTypeEnum("legal-flag")))

        self.db.session.commit()
        # test will fail if this raises exception
        CoprsLogic.raise_if_unfinished_blocking_action(self.c1, "ha, failed")

    def test_fulltext_whooshee_return_all_hits(self, f_users, f_db):
        # https://bugzilla.redhat.com/show_bug.cgi?id=1153039
        self.prefix = u"prefix"
        self.s_coprs = []

        index = Whooshee.get_or_create_index(app, CoprWhoosheer)
        writer = index.writer()

        u1_count = 150
        for x in range(u1_count):
            self.s_coprs.append(models.Copr(name=self.prefix + str(x), user=self.u1))

        u2_count = 7
        for x in range(u2_count):
            self.s_coprs.append(models.Copr(name=self.prefix + str(x), user=self.u2))

        u3_count = 9
        for x in range(u3_count):
            self.s_coprs.append(models.Copr(name=u"_wrong_" + str(x), user=self.u3))

        self.db.session.add_all(self.s_coprs)
        self.db.session.commit()

        for copr in self.s_coprs:
            CoprWhoosheer.insert_copr(writer, copr)
        writer.commit(optimize=True)

        query = CoprsLogic.get_multiple_fulltext("prefix")
        pre_query = models.Copr.query.order_by(desc(models.Copr.created_on))\
            .join(models.User).filter(models.Copr.deleted == False)

        query = pre_query.whooshee_search(self.prefix, whoosheer=CoprWhoosheer) # needs flask-whooshee-0.2.0

        results = query.all()
        for obj in results:
            assert self.prefix in obj.name

        obtained = len(results)
        expected = u1_count + u2_count

        assert obtained == expected

    def test_raise_if_cant_delete(self, f_users, f_fas_groups, f_coprs):
        # Project owner should be able to delete his project
        CoprsLogic.raise_if_cant_delete(self.u2, self.c2)

        # Admin should be able to delete everything
        CoprsLogic.raise_if_cant_delete(self.u1, self.c2)

        # A user can't remove someone else's project
        with pytest.raises(InsufficientRightsException):
            CoprsLogic.raise_if_cant_delete(self.u2, self.c1)

        # Group member should be able to remove group project
        self.u2.openid_groups = {"fas_groups": ["somegroup"]}
        self.u3.openid_groups = {"fas_groups": ["somegroup"]}

        self.c2.group = UsersLogic.get_group_by_fas_name_or_create("somegroup")
        CoprsLogic.raise_if_cant_delete(self.u3, self.c2)

        # Once a member is kicked from a group, he can't delete
        # a project even though he originally created it
        self.u2.openid_groups = {"fas_groups": []}
        with pytest.raises(InsufficientRightsException):
            CoprsLogic.raise_if_cant_delete(self.u2, self.c2)

    @new_app_context
    @mock.patch("flask.g")
    def test_copr_logic_add_sends_create_gpg_key_action(self, mc_flask_g, f_users, f_mock_chroots, f_db):
        name = u"project_1"
        selected_chroots = [self.mc1.name]

        mc_flask_g.user = self.u1
        CoprsLogic.add(self.u1, name, selected_chroots)
        self.db.session.commit()

        actions = ActionsLogic.get_many(ActionTypeEnum("gen_gpg_key")).all()
        assert len(actions) == 1
        data = json.loads(actions[0].data)
        assert data["ownername"] == self.u1.name
        assert data["projectname"] == name


class TestCoprChrootsLogic(CoprsTestCase):

    def test_update_from_names(self, f_users, f_coprs, f_mock_chroots, f_db):
        chroot_names = ["fedora-17-x86_64", "fedora-17-i386"]
        assert [ch.name for ch in self.c2.copr_chroots] == chroot_names
        CoprChrootsLogic.update_from_names(self.c2.user, self.c2, chroot_names)
        assert [ch.name for ch in self.c2.copr_chroots] == chroot_names

        chroot_names = ["fedora-17-x86_64"]
        CoprChrootsLogic.update_from_names(self.c2.user, self.c2, chroot_names)
        assert [ch.name for ch in self.c2.copr_chroots] == chroot_names

    def test_update_from_names_disabled(self, f_users, f_coprs, f_mock_chroots, f_db):
        # Say, that fedora-17-x86_64 is outdated
        self.mc2.is_active = False

        # The fedora-17-x86_64 is not a part of the copr edit form,
        # because it is outdated. See #712, PR#719
        CoprChrootsLogic.update_from_names(self.c2.user, self.c2, ["fedora-17-i386"])

        # However, it should not be removed from the Copr
        assert [ch.name for ch in self.c2.copr_chroots] == ["fedora-17-x86_64", "fedora-17-i386"]

    def test_filter_outdated(self, f_users, f_coprs, f_mock_chroots, f_db):
        outdated = CoprChrootsLogic.filter_outdated(CoprChrootsLogic.get_multiple())
        assert outdated.all() == []

        # A chroot is supposed to be removed today (without a time specification)
        # Do not notify anyone, it is already too late. For all intents and purposes,
        # the data is already gone.
        self.c2.copr_chroots[0].delete_after = date.today()
        assert outdated.all() == []

        # A chroot will be deleted tomorrow
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=1)
        assert outdated.all() == [self.c2.copr_chroots[0]]

        # A chroot was deleted yesterday
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        assert outdated.all() == []

    def test_filter_outdated_to_be_deleted(self, f_users, f_coprs, f_mock_chroots, f_db):
        outdated = CoprChrootsLogic.filter_outdated_to_be_deleted(CoprChrootsLogic.get_multiple())
        assert outdated.all() == []

        # A chroot is supposed to be removed today (without a time specification)
        self.c2.copr_chroots[0].delete_after = date.today()
        assert outdated.all() == [self.c2.copr_chroots[0]]

        # A chroot should be deleted tomorrow, don't touch it yet
        self.c2.copr_chroots[0].delete_after = datetime.today() + timedelta(days=1)
        assert outdated.all() == []

        # A chroot was supposed to be deleted yesterday, delete it
        self.c2.copr_chroots[0].delete_after = datetime.today() - timedelta(days=1)
        assert outdated.all() == [self.c2.copr_chroots[0]]

    @pytest.mark.usefixtures("f_copr_chroots_assigned")
    def test_disabling_disallowed_when_build_runs(self):
        """
        We disallow removing chroots from project when some BuildChroot(s) are
        still in progress.
        """
        chroot_names = ["fedora-17-x86_64", "fedora-17-i386"]
        assert [ch.name for ch in self.c2.copr_chroots] == chroot_names

        with pytest.raises(ConflictingRequest) as exc:
            CoprChrootsLogic.update_from_names(self.c2.user, self.c2, ["fedora-17-x86_64"])
        assert "builds 3 and 4 are still in progress" in exc.value.message
        for bch in self.b3_bc:
            bch.status = StatusEnum("failed")
        for bch in self.b4_bc:
            bch.status = StatusEnum("succeeded")
        CoprChrootsLogic.update_from_names(self.c2.user, self.c2, ["fedora-17-x86_64"])

    @pytest.mark.usefixtures("f_copr_chroots_assigned_finished")
    def test_chroot_reenable(self):
        """
        We re-assign old unassigned BuildChroots to newly created
        CoprChroot instances if they match the corresponding MockChroot
        """
        assert len(self.c2.copr_chroots) == 2
        assert self.mc3 in self.c2.mock_chroots
        old_copr_chroot = self.c2.copr_chroots[1]
        old_bch_ids = [bch.id_ for bch in old_copr_chroot.build_chroots]
        CoprChrootsLogic.update_from_names(self.c2.user, self.c2, ["fedora-17-x86_64"])
        assert len(self.c2.copr_chroots) == 1
        assert self.mc3 not in self.c2.mock_chroots

        # re-enable
        CoprChrootsLogic.update_from_names(
            self.c2.user, self.c2, ["fedora-17-x86_64", "fedora-17-i386"])

        new_copr_chroot = self.c2.copr_chroots[1]
        assert old_copr_chroot != new_copr_chroot
        assert old_bch_ids == [bch.id_ for bch in new_copr_chroot.build_chroots]


class TestPinnedCoprsLogic(CoprsTestCase):

    def test_pinned_projects(self, f_users, f_coprs, f_db):
        assert set(CoprsLogic.get_multiple_by_username(self.u2.name)) == {self.c2, self.c3}
        assert set(PinnedCoprsLogic.get_by_owner(self.u2)) == set()

        pc1 = models.PinnedCoprs(id=1, copr_id=self.c2.id, user_id=self.u2.id, position=1)
        pc2 = models.PinnedCoprs(id=2, copr_id=self.c3.id, user_id=self.u2.id, position=2)
        self.db.session.add_all([pc1, pc2])

        assert set(PinnedCoprsLogic.get_by_owner(self.u2)) == {pc1, pc2}
        assert set(CoprsLogic.get_multiple_by_username(self.u2.name)) == {self.c2, self.c3}

    def test_limit(self):
        app.config["PINNED_PROJECTS_LIMIT"] = 1
        with app.app_context():
            form = PinnedCoprsForm()
            form.copr_ids.data = ["1"]
            assert form.validate()

            form.copr_ids.data = ["1", "2"]
            assert not form.validate()
            assert "Too many" in form.errors["coprs"][0]

    def test_unique_coprs(self):
        app.config["PINNED_PROJECTS_LIMIT"] = 2
        with app.app_context():
            form = PinnedCoprsForm()
            form.copr_ids.data = ["1", "1"]
            assert not form.validate()
            assert "only once" in form.errors["coprs"][0]

    def test_delete_project_that_is_pinned(self, f_users, f_coprs, f_db):
        pc1 = models.PinnedCoprs(id=1, copr_id=self.c2.id, user_id=self.u2.id, position=1)
        pc2 = models.PinnedCoprs(id=2, copr_id=self.c3.id, user_id=self.u2.id, position=2)
        self.db.session.add_all([pc1, pc2])

        ComplexLogic.delete_copr(self.c2, admin_action=True)
        assert set(CoprsLogic.get_multiple_by_username(self.u2.name)) == {self.c3}
        assert set(PinnedCoprsLogic.get_by_owner(self.u2)) == {pc2}

class TestChrootFormLogic(CoprsTestCase):

    def test_module_toggle_format(self):
        with app.app_context():
            form = ChrootForm()
            form.module_toggle.data = "module:stream"
            assert form.validate()

            form.module_toggle.data = ""
            assert form.validate()

            form.module_toggle.data = "module:stream, module1:stream1"
            assert form.validate()

            form.module_toggle.data = "module"
            assert False == form.validate()

            form.module_toggle.data = "module 1:stream"
            assert False == form.validate()

            form.module_toggle.data = "module: stream"
            assert False == form.validate()
