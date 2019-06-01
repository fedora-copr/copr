import json
import datetime

from flask_whooshee import Whooshee

from copr_common.enums import ActionTypeEnum
from coprs import app
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.coprs_logic import CoprsLogic, CoprChrootsLogic

from coprs import models
from coprs.whoosheers import CoprWhoosheer
from tests.coprs_test_case import CoprsTestCase


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
        pre_query = models.Copr.query.join(models.User).filter(models.Copr.deleted == False)

        query = pre_query.whooshee_search(self.prefix, whoosheer=CoprWhoosheer) # needs flask-whooshee-0.2.0

        results = query.all()
        for obj in results:
            assert self.prefix in obj.name

        obtained = len(results)
        expected = u1_count + u2_count

        assert obtained == expected

    def test_copr_logic_add_sends_create_gpg_key_action(self, f_users, f_mock_chroots, f_db):
        name = u"project_1"
        selected_chroots = [self.mc1.name]

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
