from collections import defaultdict
import json
import os
import pprint
import time
from sqlalchemy import or_
from sqlalchemy import and_

from sqlalchemy.orm.exc import NoResultFound

from coprs import app
from coprs import db
from coprs import exceptions
from coprs.models import CounterStat
from coprs import helpers
from coprs.helpers import REPO_DL_STAT_FMT
from coprs import signals
from coprs.helpers import CounterStatType




class CounterStatLogic(object):

    @classmethod
    def get(cls, name):
        """
        :param name: counter name
        :return:
        """
        return CounterStat.query.filter(CounterStat.name == name)

    @classmethod
    def get_multiply_same_type(cls, counter_type, names_list):
        return (
            CounterStat.query
            .filter(CounterStat.counter_type == counter_type)
            .filter(CounterStat.name.in_(names_list))
        )

    @classmethod
    def add(cls, name, counter_type):
        csl = CounterStat(name=name, counter_type=counter_type)
        db.session.add(csl)
        return csl

    @classmethod
    def incr(cls, name, counter_type):
        """
        Warning: dirty method: does commit if missing stat record.
        """
        try:
            csl = CounterStatLogic.get(name).one()
            csl.counter = CounterStat.counter + 1
        except NoResultFound:
            csl = CounterStatLogic.add(name, counter_type)
            csl.counter = 1

        db.session.add(csl)
        return csl

    @classmethod
    def get_copr_repo_dl_stat(cls, copr):
        # chroot -> stat_name
        chroot_by_stat_name = {}
        for chroot in copr.active_chroots:
            kwargs = {
                "user": copr.owner.name,
                "copr": copr.name,
                "name_release": chroot.name_release
            }
            chroot_by_stat_name[REPO_DL_STAT_FMT.format(**kwargs)] = chroot.name_release

        # [{counter: <value>, name: <stat_name>}, ...]
        stats = cls.get_multiply_same_type(counter_type=helpers.CounterStatType.REPO_DL,
                                           names_list=chroot_by_stat_name.keys())

        # need: {chroot -> value, ... }
        repo_dl_stats = defaultdict(int)
        for stat in stats:
            repo_dl_stats[chroot_by_stat_name[stat.name]] = stat.counter

        return repo_dl_stats





