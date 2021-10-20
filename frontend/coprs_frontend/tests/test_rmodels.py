"""
Test the class TimedStatEvents
"""

import time

from coprs.rmodels import TimedStatEvents
from coprs import rcp


class TestRModels:
    rc = None  # pylint: disable=invalid-name
    disabled = None
    prefix = "copr:test:r_models"
    time_now = None

    def setup_method(self):
        self.rc = rcp.get_connection()
        self.rc.ping()
        self.time_now = time.time()

    def teardown_method(self):
        keys = self.rc.keys('{}*'.format(self.prefix))
        if keys:
            self.rc.delete(*keys)

    def test_timed_stats_events(self):
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
