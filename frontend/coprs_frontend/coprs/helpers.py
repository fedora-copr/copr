import math
import random
import string
import urlparse
import flask

from dateutil import parser as dt_parser
from netaddr import IPAddress, IPNetwork

from redis import StrictRedis

from coprs import constants, app
from coprs import app

from rpmUtils.miscutils import splitFilename


def generate_api_token(size=30):
    """ Generate a random string used as token to access the API
    remotely.

    :kwarg: size, the size of the token to generate, defaults to 30
        chars.
    :return: a string, the API token for the user.
    """
    return ''.join(random.choice(string.ascii_lowercase) for x in range(size))


REPO_DL_STAT_FMT = "repo_dl_stat::{copr_user}@{copr_project_name}:{copr_name_release}"
CHROOT_REPO_MD_DL_STAT_FMT = "chroot_repo_metadata_dl_stat:hset::{copr_user}@{copr_project_name}:{copr_chroot}"
CHROOT_RPMS_DL_STAT_FMT = "chroot_rpms_dl_stat:hset::{copr_user}@{copr_project_name}:{copr_chroot}"
PROJECT_RPMS_DL_STAT_FMT = "project_rpms_dl_stat:hset::{copr_user}@{copr_project_name}"


class CounterStatType(object):
    REPO_DL = "repo_dl"


class EnumType(type):

    def __call__(self, attr):
        if isinstance(attr, int):
            for k, v in self.vals.items():
                if v == attr:
                    return k
            raise KeyError("num {0} is not mapped".format(attr))
        else:
            return self.vals[attr]


class PermissionEnum(object):
    __metaclass__ = EnumType
    vals = {"nothing": 0, "request": 1, "approved": 2}

    @classmethod
    def choices_list(cls, without=-1):
        return [(n, k) for k, n in cls.vals.items() if n != without]


class ActionTypeEnum(object):
    __metaclass__ = EnumType
    vals = {
        "delete": 0,
        "rename": 1,
        "legal-flag": 2,
        "createrepo": 3,
    }


class BackendResultEnum(object):
    __metaclass__ = EnumType
    vals = {"waiting": 0, "success": 1, "failure": 2}


class RoleEnum(object):
    __metaclass__ = EnumType
    vals = {"user": 0, "admin": 1}


class StatusEnum(object):
    __metaclass__ = EnumType
    vals = {"failed": 0,
            "succeeded": 1,
            "canceled": 2,
            "running": 3,
            "pending": 4,
            "skipped": 5,  # if there was this package built already
            "starting": 6,  # build picked by worker but no VM initialized
            "importing": 7} # SRPM is being imported to dist-git


class BuildSourceEnum(object):
    __metaclass__ = EnumType
    vals = {"unset": 0,
            "srpm_link": 1,  # url
            "srpm_upload": 2}  # pkg, tmp


class Paginator(object):

    def __init__(self, query, total_count, page=1,
                 per_page_override=None, urls_count_override=None):

        self.query = query
        self.total_count = total_count
        self.page = page
        self.per_page = per_page_override or constants.ITEMS_PER_PAGE
        self.urls_count = urls_count_override or constants.PAGES_URLS_COUNT
        self._sliced_query = None

    def page_slice(self, page):
        return (self.per_page * (page - 1),
                self.per_page * page)

    @property
    def sliced_query(self):
        if not self._sliced_query:
            self._sliced_query = self.query[slice(*self.page_slice(self.page))]
        return self._sliced_query

    @property
    def pages(self):
        return int(math.ceil(self.total_count / float(self.per_page)))

    def border_url(self, request, start):
        if start:
            if self.page - 1 > self.urls_count / 2:
                return self.url_for_other_page(request, 1), 1
        else:
            if self.page < self.pages - self.urls_count / 2:
                return self.url_for_other_page(request, self.pages), self.pages

        return None

    def get_urls(self, request):
        left_border = self.page - self.urls_count / 2
        left_border = 1 if left_border < 1 else left_border
        right_border = self.page + self.urls_count / 2
        right_border = self.pages if right_border > self.pages else right_border

        return [(self.url_for_other_page(request, i), i)
                for i in range(left_border, right_border + 1)]

    def url_for_other_page(self, request, page):
        args = request.view_args.copy()
        args["page"] = page
        return flask.url_for(request.endpoint, **args)


def chroot_to_branch(chroot):
    """
    Get a git branch name from chroot. Follow the fedora naming standard.
    """
    os, version, arch = chroot.split("-")
    if os == "fedora":
        if version == "rawhide":
            return "master"
        os = "f"
    elif os == "epel" and int(version) <= 6:
        os = "el"
    return "{}{}".format(os, version)

def branch_to_os_version(branch):
    os = None
    version = None
    if branch == "master":
        os = "fedora"
        version = "rawhide"
    elif branch[0] == "f":
        os = "fedora"
        version = branch[1:]
    elif branch[:4] == "epel" or branch[:2] == "el":
        os = "epel"
        version = branch[-1:]
    return os, version


def parse_package_name(pkg):
    """
    Parse package name from possibly incomplete nvra string.
    """

    if pkg.count(".") >= 3 and pkg.count("-") >= 2:
        return splitFilename(pkg)[0]

    # doesn"t seem like valid pkg string, try to guess package name
    result = ""
    pkg = pkg.replace(".rpm", "").replace(".src", "")

    for delim in ["-", "."]:
        if delim in pkg:
            parts = pkg.split(delim)
            for part in parts:
                if any(map(lambda x: x.isdigit(), part)):
                    return result[:-1]

                result += part + "-"

            return result[:-1]

    return pkg


def generate_repo_url(mock_chroot, url):
    """ Generates url with build results for .repo file.
    No checks if copr or mock_chroot exists.
    """
    if mock_chroot.os_release == "fedora":
        if mock_chroot.os_version != "rawhide":
            mock_chroot.os_version = "$releasever"

    url = urlparse.urljoin(
        url, "{0}-{1}-{2}/".format(mock_chroot.os_release,
                                   mock_chroot.os_version, "$basearch"))

    return url


def fix_protocol_for_backend(url):
    """
    Ensure that url either has http or https protocol according to the
    option in app config "ENFORCE_PROTOCOL_FOR_BACKEND_URL"
    """
    if app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] == "https":
        return url.replace("http://", "https://")
    elif app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] == "http":
        return url.replace("https://", "http://")
    else:
        return url


def fix_protocol_for_frontend(url):
    """
    Ensure that url either has http or https protocol according to the
    option in app config "ENFORCE_PROTOCOL_FOR_FRONTEND_URL"
    """
    if app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] == "https":
        return url.replace("http://", "https://")
    elif app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] == "http":
        return url.replace("https://", "http://")
    else:
        return url


class Serializer(object):

    def to_dict(self, options=None):
        """
        Usage:

        SQLAlchObject.to_dict() => returns a flat dict of the object
        SQLAlchObject.to_dict({"foo": {}}) => returns a dict of the object
            and will include a flat dict of object foo inside of that
        SQLAlchObject.to_dict({"foo": {"bar": {}}, "spam": {}}) => returns
            a dict of the object, which will include dict of foo
            (which will include dict of bar) and dict of spam.

        Options can also contain two special values: __columns_only__
        and __columns_except__

        If present, the first makes only specified fiels appear,
        the second removes specified fields. Both of these fields
        must be either strings (only works for one field) or lists
        (for one and more fields).

        SQLAlchObject.to_dict({"foo": {"__columns_except__": ["id"]},
            "__columns_only__": "name"}) =>

        The SQLAlchObject will only put its "name" into the resulting dict,
        while "foo" all of its fields except "id".

        Options can also specify whether to include foo_id when displaying
        related foo object (__included_ids__, defaults to True).
        This doesn"t apply when __columns_only__ is specified.
        """

        result = {}
        if options is None:
            options = {}
        columns = self.serializable_attributes

        if "__columns_only__" in options:
            columns = options["__columns_only__"]
        else:
            columns = set(columns)
            if "__columns_except__" in options:
                columns_except = options["__columns_except__"]
                if not isinstance(options["__columns_except__"], list):
                    columns_except = [options["__columns_except__"]]

                columns -= set(columns_except)

            if ("__included_ids__" in options and
                    options["__included_ids__"] is False):

                related_objs_ids = [
                    r + "_id" for r, _ in options.items()
                    if not r.startswith("__")]

                columns -= set(related_objs_ids)

            columns = list(columns)

        for column in columns:
            result[column] = getattr(self, column)

        for related, values in options.items():
            if hasattr(self, related):
                result[related] = getattr(self, related).to_dict(values)
        return result

    @property
    def serializable_attributes(self):
        return map(lambda x: x.name, self.__table__.columns)


class RedisConnectionProvider(object):
    def __init__(self, config):
        self.host = config.get("redis_host", "127.0.0.1")
        self.port = int(config.get("redis_port", "6379"))

    def get_connection(self):
        return StrictRedis(host=self.host, port=self.port)


def get_redis_connection():
    """
    Creates connection to redis, now we use default instance at localhost, no config needed
    """
    return StrictRedis()


def dt_to_unixtime(dt):
    """
    Converts datetime to unixtime
    :param dt: DateTime instance
    :rtype: float
    """
    return float(dt.strftime('%s'))


def string_dt_to_unixtime(dt_string):
    """
    Converts datetime to unixtime from string
    :param dt_string: datetime string
    :rtype: str
    """
    return dt_to_unixtime(dt_parser.parse(dt_string))


def is_ip_from_builder_net(ip):
    """
    Checks is ip is owned by the builders network
    :param str ip: IPv4 address
    :return bool: True
    """
    ip_addr = IPAddress(ip)
    for subnet in app.config.get("BUILDER_IPS", ["127.0.0.1/24"]):
        if ip_addr in IPNetwork(subnet):
            return True

    return False
