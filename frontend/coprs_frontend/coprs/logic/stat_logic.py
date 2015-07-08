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
from coprs.helpers import REPO_DL_STAT_FMT, CHROOT_REPO_MD_DL_STAT_FMT, dt_to_unixtime, string_dt_to_unixtime, \
    CHROOT_RPMS_DL_STAT_FMT, PROJECT_RPMS_DL_STAT_FMT
from coprs.helpers import CounterStatType
from coprs.rmodels import TimedStatEvents


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
                "copr_user": copr.owner.name,
                "copr_project_name": copr.name,
                "copr_name_release": chroot.name_release
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


def handle_logstash(rc, ls_data):
    """
    :param rc: connection to redis
    :type rc: StrictRedis

    :param ls_data: log stash record
    :type ls_data: dict
    """
    dt_unixtime = string_dt_to_unixtime(ls_data["@timestamp"])
    app.logger.debug("got ls_data: {}".format(ls_data))

    if "tags" in ls_data:
        tags = set(ls_data["tags"])
        if "frontend" in tags and "repo_dl":
            name = REPO_DL_STAT_FMT.format(**ls_data)
            CounterStatLogic.incr(name=name, counter_type=CounterStatType.REPO_DL)
            db.session.commit()

        if "backend" in tags and "repomdxml" in tags:
            key = CHROOT_REPO_MD_DL_STAT_FMT.format(**ls_data)
            TimedStatEvents.add_event(rc, key, timestamp=dt_unixtime)

        if "backend" in tags and "rpm" in tags:
            key_chroot = CHROOT_RPMS_DL_STAT_FMT.format(**ls_data)
            key_project = PROJECT_RPMS_DL_STAT_FMT.format(**ls_data)
            TimedStatEvents.add_event(rc, key_chroot, timestamp=dt_unixtime)
            TimedStatEvents.add_event(rc, key_project, timestamp=dt_unixtime)
