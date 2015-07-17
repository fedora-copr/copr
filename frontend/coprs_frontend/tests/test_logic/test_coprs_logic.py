import pytest

from coprs.exceptions import ActionInProgressException
from coprs.helpers import ActionTypeEnum
from coprs.logic.coprs_logic import CoprsLogic

from coprs import models
from tests.coprs_test_case import CoprsTestCase


class TestCoprsLogic(CoprsTestCase):

    def test_update_raises_if_copr_has_unfinished_actions(self, f_users,
                                                          f_coprs, f_actions,
                                                          f_db):
        self.c1.name = "foo"
        with pytest.raises(ActionInProgressException):
            CoprsLogic.update(self.u1, self.c1)
        self.db.session.rollback()

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

        u1_count = 150
        for x in range(u1_count):
            self.s_coprs.append(models.Copr(name=self.prefix + str(x), owner=self.u1))

        u2_count = 7
        for x in range(u2_count):
            self.s_coprs.append(models.Copr(name=self.prefix + str(x), owner=self.u2))

        u3_count = 9
        for x in range(u3_count):
            self.s_coprs.append(models.Copr(name=u"_wrong_" + str(x), owner=self.u3))

        self.db.session.add_all(self.s_coprs)
        self.db.session.commit()

        # query = CoprsLogic.get_multiple_fulltext("prefix")
        pre_query = models.Copr.query.join(models.User).filter(models.Copr.deleted == False)

        query = pre_query.whooshee_search(self.prefix)

        results = query.all()
        for obj in results:
            assert self.prefix in obj.name

        obtained = len(results)
        expected = u1_count + u2_count
        # TODO: uncomment after fix in flask-whooshee will be released
        # assert obtained == expected
