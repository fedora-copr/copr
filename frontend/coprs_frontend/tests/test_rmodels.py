# coding: utf-8

import time

from redis import StrictRedis, ConnectionError

from coprs.rmodels import TimedStatEvents


class TestRModels(object):

    def setup_method(self, method):
        self.rc = StrictRedis()
        self.disabled = False
        try:
            self.rc.ping()
        except ConnectionError:
            self.disabled = True
        self.prefix = "copr:test:r_models"

        self.time_now = time.time()

    def teardown_method(self, method):
        if self.disabled:
            return

        keys = self.rc.keys('{}*'.format(self.prefix))
        if keys:
            self.rc.delete(*keys)

    def test_timed_stats_events(self):
        if self.disabled:
            return

        TimedStatEvents.add_event(self.rc, name="foobar", prefix=self.prefix,
                                  timestamp=self.time_now, )

        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,) == 1
        TimedStatEvents.add_event(self.rc, name="foobar", prefix=self.prefix,
                                  timestamp=self.time_now, count=2)

        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,) == 3

        TimedStatEvents.add_event(self.rc, name="foobar", prefix=self.prefix,
                                  timestamp=self.time_now - 1000000, count=2)
        TimedStatEvents.add_event(self.rc, name="foobar", prefix=self.prefix,
                                  timestamp=self.time_now - 3000000, count=3)

        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,) == 3
        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,
                                         day_min=self.time_now - 2000000) == 5
        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,
                                         day_min=self.time_now - 5000000) == 8

        TimedStatEvents.trim_before(self.rc, name="foobar",
                                    prefix=self.prefix, threshold_timestamp=self.time_now - 200000)

        assert TimedStatEvents.get_count(self.rc, name="foobar", prefix=self.prefix,
                                         day_min=self.time_now - 5000000) == 3

