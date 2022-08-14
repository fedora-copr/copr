from collections import defaultdict

from sqlalchemy.orm.exc import NoResultFound

from coprs import app
from coprs import db
from coprs.models import CounterStat
from coprs import helpers, models


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
    def incr(cls, name, counter_type, count=1):
        """
        Warning: dirty method: does commit if missing stat record.
        """
        try:
            csl = CounterStatLogic.get(name).one()
            csl.counter = CounterStat.counter + count
        except NoResultFound:
            csl = CounterStatLogic.add(name, counter_type)
            csl.counter = count

        db.session.add(csl)
        return csl

    @classmethod
    def get_copr_repo_dl_stat(cls, copr):
        # chroot -> stat_name
        chroot_by_stat_name = {}
        for chroot in copr.active_chroots:
            stat_name = helpers.get_stat_name(
                stat_type=helpers.CounterStatType.REPO_DL,
                copr_dir=copr.main_dir,
                name_release=chroot.name_release,
            )
            chroot_by_stat_name[stat_name] = chroot.name_release

        # [{counter: <value>, name: <stat_name>}, ...]
        stats = cls.get_multiply_same_type(counter_type=helpers.CounterStatType.REPO_DL,
                                           names_list=chroot_by_stat_name.keys())

        # need: {chroot -> value, ... }
        repo_dl_stats = defaultdict(int)
        for stat in stats:
            repo_dl_stats[chroot_by_stat_name[stat.name]] = stat.counter

        return repo_dl_stats

    @classmethod
    def get_popular_projects(cls):
        """
        Return CounterStat results for projects with the most downloaded RPMs
        """
        return cls.get_popular(helpers.CounterStatType.PROJECT_RPMS_DL)

    @classmethod
    def get_popular_chroots(cls):
        """
        Return CounterStat results for chroots with the most downloaded RPMs
        """
        return cls.get_popular(helpers.CounterStatType.CHROOT_RPMS_DL)

    @classmethod
    def get_popular(cls, counter_type, limit=10):
        """
        Return CounterStat results with the highest counter for a given
        CounterStatType.
        """
        return (CounterStat.query
                .filter(CounterStat.counter_type == counter_type)
                .order_by(models.CounterStat.counter.desc())
                .limit(limit))


def handle_be_stat_message(stat_data):
    """
    :param stat_data: stats from backend
    :type stat_data: dict
    """
    app.logger.debug('Got stat data: {}'.format(stat_data))

    hits = stat_data['hits']
    for key_str, count in hits.items():
        stat_type, key_string = key_str.split("|", 1)

        # FIXME the keys from backend doesn't match CounterStatType exactly
        stat_type = stat_type.rstrip("_stat")

        assert stat_type in [
            helpers.CounterStatType.REPO_DL,
            helpers.CounterStatType.CHROOT_REPO_MD_DL,
            helpers.CounterStatType.CHROOT_RPMS_DL,
            helpers.CounterStatType.PROJECT_RPMS_DL,
        ]

        stat_name = helpers.get_stat_name(
            stat_type=stat_type,
            key_string=key_string,
        )
        CounterStatLogic.incr(stat_name, stat_type, count)
