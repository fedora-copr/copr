from __future__ import absolute_import

from functools import wraps
import os
import time
import configparser
from munch import Munch
from .exceptions import CoprConfigException, CoprException


class List(list):
    def __init__(self, items, meta=None, response=None, proxy=None):
        list.__init__(self, items)
        self.meta = meta
        self.__response__ = response
        self.__proxy__ = proxy


def config_from_file(path=None):
    raw_config = configparser.ConfigParser()

    config = {}
    default_path = os.path.join("~", ".config", "copr")

    try:
        exists = raw_config.read(os.path.expanduser(path or default_path))
    except configparser.Error as ex:
        raise CoprConfigException(str(ex))

    if not exists:
        if path:
            # absence of the default_path is acceptable, but missing the
            # explicitly specified path= argument deserves an exception.
            raise CoprConfigException("File {0} is missing.".format(path))
        raw_config["copr-cli"] = {"copr_url": "https://copr.fedorainfracloud.org"}

    try:
        for field in ["username", "login", "token", "copr_url", "gssapi"]:
            config[field] = raw_config["copr-cli"].get(field, None)
        config["encrypted"] = raw_config["copr-cli"].getboolean("encrypted", True)
        config["gssapi"] = raw_config["copr-cli"].getboolean("gssapi")


    except configparser.Error as err:
        raise CoprConfigException("Bad configuration file: {0}".format(err))

    if config["encrypted"] and config["copr_url"].startswith("http://"):
        raise CoprConfigException("The `copr_url` should not be http, please obtain "
                                  "an up-to-date configuration from the Copr website")

    return config


def for_all_methods(decorator):
    """
    Apply a given decorator to all class methods
    """
    def decorate(cls):
        for attr in list(cls.__dict__):
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate


def bind_proxy(func):
    """
    Modify a result munch and set the __proxy__ parameter
    to the actual proxy instance.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if type(result) not in [List, Munch]:
            return result
        result.__proxy__ = args[0]
        return result
    return wrapper


def wait(waitable, interval=30, callback=None, timeout=0):
    """
    Wait for a waitable thing to finish. At this point, it is possible to wait only
    for builds, but this function should be enhanced to wait for
    e.g. modules or images, etc in the future

    :param Munch/list waitable: A Munch result or list of munches
    :param int interval: How many seconds wait before requesting updated Munches from frontend
    :param callable callback: Callable taking one argument (list of build Munches).
                              It will be triggered before every sleep interval.
    :param int timeout: Limit how many seconds should be waited before this function unsuccessfully ends
    :return: list of build Munches

    Example usage:

        build1 = client.build_proxy.create_from_file(...)
        build2 = client.build_proxy.create_from_scm(...)
        wait([build1, build2])

    """
    builds = waitable if isinstance(waitable, list) else [waitable]
    watched = set([build.id for build in builds])
    munches = dict((build.id, build) for build in builds)
    failed = []
    terminate = time.time() + timeout

    while True:
        for build_id in watched.copy():
            if hasattr(munches[build_id], "__proxy__"):
                proxy = munches[build_id].__proxy__
            else:
                proxy = waitable.__proxy__
            build = munches[build_id] = proxy.get(build_id)

            if build.state in ["failed"]:
                failed.append(build_id)
            if build.state in ["succeeded", "skipped", "failed", "canceled"]:
                watched.remove(build_id)
            if build.state == "unknown":
                raise CoprException("Unknown status.")

        if callback:
            callback(list(munches.values()))
        if not watched:
            break
        if timeout and time.time() >= terminate:
            raise CoprException("Timeouted")
        time.sleep(interval)
    return list(munches.values())


def succeeded(builds):
    """
    Determine, whether the list of builds finished successfully.

    :param Munch/list builds: A list of builds or a single build Munch
    :return bool:
    """
    builds = builds if type(builds) == list else [builds]
    for build in builds:
        if build.state != "succeeded":
            return False
    return True
