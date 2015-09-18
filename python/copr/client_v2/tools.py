# coding: utf-8
import time
from copr.client_v2.resources import Build


def wait_for_builds(builds, check_timeout=30):
    """
    :type builds: list of Build
    :param time check_timeout: delay between status check attempts
    """

    if isinstance(builds, Build):
        builds = [builds]

    working = list(builds)
    while len(working) > 0:
        next_gen = []
        for b in working:
            if not b.get_self().is_finished():
                next_gen.append(b)
        working = next_gen
        time.sleep(check_timeout)
