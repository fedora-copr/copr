# coding: utf-8
import pytest

from coprs.logic.stat_logic import CounterStatLogic
from coprs.helpers  import CounterStatType
from tests.coprs_test_case import CoprsTestCase


class TestStatLogic(CoprsTestCase):

    def setup_method(self, method):
        super(TestStatLogic, self).setup_method(method)

        self.counter_type = CounterStatType.REPO_DL
        self.counter_name = "{}:user/copr".format(CounterStatType.REPO_DL)

    def test_counter_basic(self):
        CounterStatLogic.add(self.counter_name, self.counter_type)
        self.db.session.commit()
        CounterStatLogic.incr(self.counter_name, self.counter_type)
        self.db.session.commit()
        csl = CounterStatLogic.get(self.counter_name).one()
        assert csl.counter == 1

    def test_new_by_incr(self):
        with pytest.raises(Exception):
            CounterStatLogic.get(self.counter_name).one()

        CounterStatLogic.incr(self.counter_name, self.counter_type)
        self.db.session.commit()
        csl = CounterStatLogic.get(self.counter_name).one()
        assert csl.counter == 1
