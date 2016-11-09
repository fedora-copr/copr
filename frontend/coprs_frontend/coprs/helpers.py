import math
import random
import string

from six import with_metaclass
from six.moves.urllib.parse import urljoin, urlparse
import pipes
from textwrap import dedent
import re

import flask
from flask import url_for
from dateutil import parser as dt_parser
from netaddr import IPAddress, IPNetwork
from redis import StrictRedis
from sqlalchemy.types import TypeDecorator, VARCHAR
import json

from coprs import constants
from coprs import app


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


class PermissionEnum(with_metaclass(EnumType, object)):
    vals = {"nothing": 0, "request": 1, "approved": 2}

    @classmethod
    def choices_list(cls, without=-1):
        return [(n, k) for k, n in cls.vals.items() if n != without]


class ActionTypeEnum(with_metaclass(EnumType, object)):
    vals = {
        "delete": 0,
        "rename": 1,
        "legal-flag": 2,
        "createrepo": 3,
        "update_comps": 4,
        "gen_gpg_key": 5,
        "rawhide_to_release": 6,
        "fork": 7,
        "update_module_md": 8,
        "build_module": 9,
    }


class BackendResultEnum(with_metaclass(EnumType, object)):
    vals = {"waiting": 0, "success": 1, "failure": 2}


class RoleEnum(with_metaclass(EnumType, object)):
    vals = {"user": 0, "admin": 1}


class StatusEnum(with_metaclass(EnumType, object)):
    vals = {"failed": 0,
            "succeeded": 1,
            "canceled": 2,
            "running": 3,
            "pending": 4,
            "skipped": 5,  # if there was this package built already
            "starting": 6,  # build picked by worker but no VM initialized
            "importing": 7, # SRPM is being imported to dist-git
            "forked": 8, # build(-chroot) was forked
           }


class BuildSourceEnum(with_metaclass(EnumType, object)):
    vals = {"unset": 0,
            "srpm_link": 1,  # url
            "srpm_upload": 2,  # pkg, tmp
            "git_and_tito": 3, # git_url, git_dir, git_branch, tito_test
            "mock_scm": 4, # scm_type, scm_url, spec, scm_branch
            "pypi": 5, # package_name, version, python_versions
            "rubygems": 6, # gem_name
            "distgit": 7, # url, branch
           }


# The same enum is also in distgit's helpers.py
class FailTypeEnum(with_metaclass(EnumType, object)):
    vals = {"unset": 0,
            # General errors mixed with errors for SRPM URL/upload:
            "unknown_error": 1,
            "build_error": 2,
            "srpm_import_failed": 3,
            "srpm_download_failed": 4,
            "srpm_query_failed": 5,
            "import_timeout_exceeded": 6,
            # Git and Tito errors:
            "tito_general_error": 30,
            "git_clone_failed": 31,
            "git_wrong_directory": 32,
            "git_checkout_error": 33,
            "srpm_build_error": 34,
           }


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict(255)

    """

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

class Paginator(object):

    def __init__(self, query, total_count, page=1,
                 per_page_override=None, urls_count_override=None,
                 additional_params=None):

        self.query = query
        self.total_count = total_count
        self.page = page
        self.per_page = per_page_override or constants.ITEMS_PER_PAGE
        self.urls_count = urls_count_override or constants.PAGES_URLS_COUNT
        self.additional_params = additional_params or dict()

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
        args.update(self.additional_params)
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
    elif os == "mageia" and version == "cauldron":
        os = "cauldron"
        version = ""
    elif os == "mageia":
        os = "mga"
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
    elif branch[:6] == "custom":
        os = "custom"
        version = branch[-1:]
    elif branch[:3] == "mga":
        os = "mageia"
        version = branch[3:]
    elif branch[:8] == "cauldron":
        os = "mageia"
        version = "cauldron"
    return os, version


def splitFilename(filename):
    """
    Pass in a standard style rpm fullname

    Return a name, version, release, epoch, arch, e.g.::
        foo-1.0-1.i386.rpm returns foo, 1.0, 1, i386
        1:bar-9-123a.ia64.rpm returns bar, 9, 123a, 1, ia64
    """

    if filename[-4:] == '.rpm':
        filename = filename[:-4]

    archIndex = filename.rfind('.')
    arch = filename[archIndex+1:]

    relIndex = filename[:archIndex].rfind('-')
    rel = filename[relIndex+1:archIndex]

    verIndex = filename[:relIndex].rfind('-')
    ver = filename[verIndex+1:relIndex]

    epochIndex = filename.find(':')
    if epochIndex == -1:
        epoch = ''
    else:
        epoch = filename[:epochIndex]

    name = filename[epochIndex + 1:verIndex]
    return name, ver, rel, epoch, arch


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

    url = urljoin(
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
        self.host = config.get("REDIS_HOST", "127.0.0.1")
        self.port = int(config.get("REDIS_PORT", "6379"))

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


def str2bool(v):
    if v is None:
        return False
    return v.lower() in ("yes", "true", "t", "1")


def copr_url(view, copr, **kwargs):
    """
    Examine given copr and generate proper URL for the `view`

    Values of `username/group_name` and `coprname` are automatically passed as the first two URL parameters,
    and therefore you should *not* pass them manually.

    Usage:
      copr_url("coprs_ns.foo", copr)
      copr_url("coprs_ns.foo", copr, arg1='bar', arg2='baz)
    """
    if copr.is_a_group_project:
        return url_for(view, group_name=copr.group.name, coprname=copr.name, **kwargs)
    return url_for(view, username=copr.user.name, coprname=copr.name, **kwargs)


def url_for_copr_view(view, group_view, copr, **kwargs):
    if copr.is_a_group_project:
        return url_for(group_view, group_name=copr.group.name, coprname=copr.name, **kwargs)
    else:
        return url_for(view, username=copr.user.name, coprname=copr.name, **kwargs)


from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.sqltypes import String, DateTime, NullType

# python2/3 compatible.
PY3 = str is not bytes
text = str if PY3 else unicode
int_type = int if PY3 else (int, long)
str_type = str if PY3 else (str, unicode)


class StringLiteral(String):
    """Teach SA how to literalize various things."""
    def literal_processor(self, dialect):
        super_processor = super(StringLiteral, self).literal_processor(dialect)

        def process(value):
            if isinstance(value, int_type):
                return text(value)
            if not isinstance(value, str_type):
                value = text(value)
            result = super_processor(value)
            if isinstance(result, bytes):
                result = result.decode(dialect.encoding)
            return result
        return process


class LiteralDialect(DefaultDialect):
    colspecs = {
        # prevent various encoding explosions
        String: StringLiteral,
        # teach SA about how to literalize a datetime
        DateTime: StringLiteral,
        # don't format py2 long integers to NULL
        NullType: StringLiteral,
    }


def literal_query(statement):
    """NOTE: This is entirely insecure. DO NOT execute the resulting strings."""
    import sqlalchemy.orm
    if isinstance(statement, sqlalchemy.orm.Query):
        statement = statement.statement
    return statement.compile(
        dialect=LiteralDialect(),
        compile_kwargs={'literal_binds': True},
    ).string


def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(2)
    return rv


def generate_repo_prefix(copr):
    """ detect group/user repo and return appropriate prefix """
    prefix = "group_" + copr.group.name if copr.group_id else copr.owner.username
    return prefix + "-"


def generate_repo_name(repo_url):
    """ based on url, generate repo name """
    repo_url = re.sub("[^a-zA-Z0-9]", '_', repo_url)
    repo_url = re.sub("(__*)", '_', repo_url)
    repo_url = re.sub("(_*$)|^_*", '', repo_url)
    return repo_url


def pre_process_repo_url(chroot, repo_url):
    """
    Expands variables and sanitize repo url to be used for mock config
    """
    parsed_url = urlparse(repo_url)
    if parsed_url.scheme == "copr":
        user = parsed_url.netloc
        prj = parsed_url.path.split("/")[1]
        repo_url = "/".join([
            flask.current_app.config["BACKEND_BASE_URL"],
            "results", user, prj, chroot
        ]) + "/"

    repo_url = repo_url.replace("$chroot", chroot)
    repo_url = repo_url.replace("$distname", chroot.split("-")[0])

    return pipes.quote(repo_url)


def generate_build_config(copr, chroot_id):
    """ Return dict with proper build config contents """
    chroot = None
    for i in copr.copr_chroots:
        if i.mock_chroot.name == chroot_id:
            chroot = i
    if not chroot:
        return ""

    packages = "" if not chroot.buildroot_pkgs else chroot.buildroot_pkgs

    repos = [{
        "id": "copr_base",
        "url": copr.repo_url + "/{}/".format(chroot_id),
        "name": "Copr repository",
    }]
    for repo in copr.repos_list:
        repo_view = {
            "id": generate_repo_name(repo),
            "url": pre_process_repo_url(chroot_id, repo),
            "name": "Additional repo " + generate_repo_name(repo),
        }
        repos.append(repo_view)

    return {
        'project_id': generate_repo_prefix(copr) + copr.name,
        'additional_packages': packages.split(),
        'repos': repos,
        'chroot': chroot_id,
    }
