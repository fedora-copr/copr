# coding: utf-8

""" Models to redis entities """
import time
from math import ceil
from datetime import timedelta


class GenericRedisModel(object):
    _KEY_BASE = "copr:generic"

    @classmethod
    def _get_key(cls, name, prefix=None):
        if prefix:
            return "{}:{}:{}".format(prefix, cls._KEY_BASE, name)
        else:
            return "{}:{}".format(cls._KEY_BASE, name)


class TimedStatEvents(GenericRedisModel):
    """
        Wraps hset structure, where:
        **key** - name of event, fix prefix specifying events type
        **member** - bucket representing one day
        **score** - events count
    """
    _KEY_BASE = "copr:tse"

    @staticmethod
    def timestamp_to_day(ut):
        """
        :param ut: unix timestamp
        :type ut: float
        :return: name for the day bucket
        """
        td = timedelta(days=1).total_seconds()
        return int(ceil(ut / td))

    @classmethod
    def gen_days_interval(cls, min_ts, max_ts):
        """
        Generate list of days bucket names which contains
            all events between `min_ts` and `max_ts`
        :param min_ts: min unix timestamp
        :param max_ts: max unix timestamp
        :rtype: list
        """
        start_ut = cls.timestamp_to_day(min_ts)
        end_ut = cls.timestamp_to_day(max_ts)

        return range(start_ut, end_ut + 1)

    @classmethod
    def add_event(cls, rconnect, name, timestamp, count=1, prefix=None):
        """
        Stoted new event to redist
        :param rconnect: Connection to a redis
        :type rconnect: StrictRedis
        :param name: statistics name
        :param timestamp: timestamp of event
        :param count: number of events, default=1
        :param prefix: prefix for statistics, default is None
        """
        count = int(count)
        ut_day = cls.timestamp_to_day(timestamp)

        key = cls._get_key(name, prefix)

        rconnect.hincrby(key, ut_day, count)

    @classmethod
    def get_count(cls, rconnect, name, day_min=None, prefix=None, day_max=None):
        """
        Count total event occurency between day_min and day_max
        :param rconnect: Connection to a redis
        :type rconnect: StrictRedis
        :param name: statistics name
        :param day_min: default: seven days ago
        :param day_max: default: tomorrow
        :param prefix: prefix for statistics, default is None

        :rtype: int
        """
        key = cls._get_key(name, prefix)
        if day_min is None:
            day_min = time.time() - timedelta(days=7).total_seconds()

        if day_max is None:
            day_max = time.time() + timedelta(days=1).total_seconds()

        interval = cls.gen_days_interval(day_min, day_max)
        if len(interval) == 0:
            return 0

        res = rconnect.hmget(key, interval)
        return sum(int(amount) for amount in res if amount is not None)


    @classmethod
    def trim_before(cls, rconnect, name, threshold_timestamp,
                    prefix=None):
        """
        Removes all records occurred before `threshold_timestamp`
        :param rconnect: StrictRedis
        :param name: statistics name
        :param threshold_timestamp: int
        :param prefix: prefix for statistics, default is None
        """

        key = cls._get_key(name, prefix)

        threshold_day = cls.timestamp_to_day(threshold_timestamp) + 1
        all_members = rconnect.hgetall(key)
        to_del = [mb for mb in all_members.keys() if int(mb) < threshold_day]

        rconnect.hdel(key, *to_del)
