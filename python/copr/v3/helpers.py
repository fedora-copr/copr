import os
import six
import configparser
from .exceptions import CoprNoConfigException, CoprConfigException


class List(list):
    def __init__(self, items, meta=None, response=None):
        list.__init__(self, items)
        self.meta = meta
        self.__response__ = response


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
