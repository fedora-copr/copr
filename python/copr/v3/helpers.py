import os
import six
import time
import configparser
from munch import Munch
from .exceptions import CoprNoConfigException, CoprConfigException, CoprException


class List(list):
    def __init__(self, items, meta=None, response=None, proxy=None):
        list.__init__(self, items)
        self.meta = meta
        self.__response__ = response
        self.__proxy__ = proxy


def config_from_file(path=None):
    raw_config = configparser.ConfigParser()
    path = os.path.expanduser(path or os.path.join("~", ".config", "copr"))
    config = {}

    try:
        exists = raw_config.read(path)
    except configparser.Error:
        raise CoprConfigException()

    if not exists:
        raise CoprNoConfigException()

    try:
        for field in ["username", "login", "token", "copr_url"]:
            if six.PY3:
                config[field] = raw_config["copr-cli"].get(field, None)
            else:
                config[field] = raw_config.get("copr-cli", field)

    except configparser.Error as err:
        raise CoprConfigException("Bad configuration file: {0}".format(err))
    return config


def for_all_methods(cls, decorator):
    """
    Apply a given decorator to all class methods
    """
    for attr in cls.__dict__:
        if callable(getattr(cls, attr)):
            setattr(cls, attr, decorator(getattr(cls, attr)))


def bind_proxy(func):
    """
    Modify a result munch and set the __proxy__ parameter
    to the actual proxy instance.
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if type(result) not in [List, Munch]:
            return result
        result.__proxy__ = args[0]
        return result
    return wrapper


def wait(result, build_proxy, interval=30, callback=None, timeout=0):
    """
    :param Munch/list result: A Munch result or list of results
    :param int interval: How many seconds wait before requesting updated Munches from frontend
    :param callable callback: Callable taking one argument (list of build Munches).
                              It will be triggered before every sleep interval.
    :param int timeout: Limit how many seconds should be waited before this function unsuccessfully ends
    :return: list of build Munches
    """
    builds = result if type(result) == list else [result]
    watched = set([build.id for build in builds])
    munches = {build.id: build for build in builds}
    failed = []
    terminate = time.time() + timeout

    while True:
        for build_id in watched.copy():
            build = munches[build_id] = build_proxy.get(build_id)
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


def succeeded(result):
    result = result if type(result) == list else [result]
    for build in result:
        if build.state != "succeeded":
            return False
    return True
