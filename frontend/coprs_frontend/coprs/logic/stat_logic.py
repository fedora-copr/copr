import time
import json

from collections import defaultdict

from sqlalchemy.orm.exc import NoResultFound

from coprs import app
from coprs import db
from coprs.models import CounterStat
from coprs import helpers
from coprs.helpers import REPO_DL_STAT_FMT, CHROOT_REPO_MD_DL_STAT_FMT, \
    CHROOT_RPMS_DL_STAT_FMT, PROJECT_RPMS_DL_STAT_FMT, is_ip_from_builder_net
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
                "copr_user": copr.user.name,
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


def handle_be_stat_message(rc, stat_data):
    """
    :param rc: connection to redis
    :type rc: StrictRedis

    :param stat_data: stats from backend
    :type stat_data: dict
    """
    app.logger.debug('Got stat data: {}'.format(stat_data))

    ts_from = int(stat_data['ts_from'])
    ts_to = int(stat_data['ts_to'])
    hits = stat_data['hits']

    if not ts_from or not ts_to or ts_from > ts_to or not hits:
        raise Exception("Invalid or empty data received.")

    ts_from_stored = int(rc.get('handle_be_stat_message_ts_from') or 0)
    ts_to_stored = int(rc.get('handle_be_stat_message_ts_to') or 0)

    app.logger.debug('ts_from: {}'.format(ts_from))
    app.logger.debug('ts_to: {}'.format(ts_to))
    app.logger.debug('ts_from_stored: {}'.format(ts_from_stored))
    app.logger.debug('ts_to_stored: {}'.format(ts_to_stored))

    if (ts_from < ts_to_stored and ts_to > ts_from_stored):
        app.logger.debug('Time overlap with already stored data. Skipping.')
        return

    hits_formatted = defaultdict(int)
    for key_str, count in hits.items():
        key = key_str.split('|')
        if key[0] == 'chroot_repo_metadata_dl_stat':
            redis_key = CHROOT_REPO_MD_DL_STAT_FMT.format(
                copr_user=key[1],
                copr_project_name=key[2],
                copr_chroot=key[3])
        elif key[0] == 'chroot_rpms_dl_stat':
            redis_key = CHROOT_RPMS_DL_STAT_FMT.format(
                copr_user=key[1],
                copr_project_name=key[2],
                copr_chroot=key[3])
        elif key[0] == 'project_rpms_dl_stat':
            redis_key = PROJECT_RPMS_DL_STAT_FMT.format(
                copr_user=key[1],
                copr_project_name=key[2])
        else:
            raise Exception('Unknown key {}'.format(key[0]))

        hits_formatted[redis_key] += count

    for redis_key, count in hits_formatted.items():
        TimedStatEvents.add_event(rc, redis_key, count=count, timestamp=ts_to)

    rc.set('handle_be_stat_message_ts_from', ts_from)
    rc.set('handle_be_stat_message_ts_to', ts_to)
