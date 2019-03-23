import math
import random
import string

from six import with_metaclass
from six.moves.urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import re

import flask
import posixpath
from flask import url_for
from dateutil import parser as dt_parser
from netaddr import IPAddress, IPNetwork
from redis import StrictRedis
from sqlalchemy.types import TypeDecorator, VARCHAR
import json

from copr_common.enums import EnumType
from copr_common.rpm import splitFilename
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


class PermissionEnum(with_metaclass(EnumType, object)):
    vals = {"nothing": 0, "request": 1, "approved": 2}

    @classmethod
    def choices_list(cls, without=-1):
        return [(n, k) for k, n in cls.vals.items() if n != without]


class BuildSourceEnum(with_metaclass(EnumType, object)):
    vals = {"unset": 0,
            "link": 1,  # url
            "upload": 2,  # pkg, tmp, url
            "pypi": 5, # package_name, version, python_versions
            "rubygems": 6, # gem_name
            "scm": 8, # type, clone_url, committish, subdirectory, spec, srpm_build_method
            "custom": 9, # user-provided script to build sources
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
            if self.page - 1 > self.urls_count // 2:
                return self.url_for_other_page(request, 1), 1
        else:
            if self.page < self.pages - self.urls_count // 2:
                return self.url_for_other_page(request, self.pages), self.pages

        return None

    def get_urls(self, request):
        left_border = self.page - self.urls_count // 2
        left_border = 1 if left_border < 1 else left_border
        right_border = self.page + self.urls_count // 2
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
    os, version, arch = chroot.rsplit("-", 2)
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
    os_version = mock_chroot.os_version

    if mock_chroot.os_release == "fedora":
        if mock_chroot.os_version != "rawhide":
            os_version = "$releasever"

    if mock_chroot.os_release == "opensuse-leap":
        os_version = "$releasever"

    if mock_chroot.os_release == "mageia":
        if mock_chroot.os_version != "cauldron":
            os_version = "$releasever"

    url = posixpath.join(
        url, "{0}-{1}-{2}/".format(mock_chroot.os_release,
                                   os_version, "$basearch"))

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

        If present, the first makes only specified fields appear,
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


def url_for_copr_builds(copr):
    return copr_url("coprs_ns.copr_builds", copr)


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
    """NOTE: This is entirely insecure. DO NOT execute the resulting strings.
       This can be used for debuggin - it is not and should not be used in production
       code.

       It is useful if you want to debug an sqlalchemy query, i.e. copy the
       resulting SQL query into psql console and try to tweak it so that it
       actually works or works faster.
    """
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
    query = parse_qs(parsed_url.query)

    if parsed_url.scheme == "copr":
        user = parsed_url.netloc
        prj = parsed_url.path.split("/")[1]
        repo_url = "/".join([
            flask.current_app.config["BACKEND_BASE_URL"],
            "results", user, prj, chroot
        ]) + "/"

    elif "priority" in query:
        query.pop("priority")
        query_string = urlencode(query, doseq=True)
        parsed_url = parsed_url._replace(query=query_string)
        repo_url = urlunparse(parsed_url)

    repo_url = repo_url.replace("$chroot", chroot)
    repo_url = repo_url.replace("$distname", chroot.rsplit("-", 2)[0])
    return repo_url


def parse_repo_params(repo, supported_keys=None):
    """
    :param repo: str repo from Copr/CoprChroot/Build/...
    :param supported_keys list of supported optional parameters
    :return: dict of optional parameters parsed from the repo URL
    """
    supported_keys = supported_keys or ["priority"]
    params = {}
    qs = parse_qs(urlparse(repo).query)
    for k, v in qs.items():
        if k in supported_keys:
            # parse_qs returns values as lists, but we allow setting the param only once,
            # so we can take just first value from it
            value = int(v[0]) if v[0].isnumeric() else v[0]
            params[k] = value
    return params


def generate_build_config(copr, chroot_id):
    """ Return dict with proper build config contents """
    chroot = None
    for i in copr.copr_chroots:
        if i.mock_chroot.name == chroot_id:
            chroot = i
    if not chroot:
        return {}

    packages = "" if not chroot.buildroot_pkgs else chroot.buildroot_pkgs

    repos = [{
        "id": "copr_base",
        "baseurl": copr.repo_url + "/{}/".format(chroot_id),
        "name": "Copr repository",
    }]

    if not copr.auto_createrepo:
        repos.append({
            "id": "copr_base_devel",
            "baseurl": copr.repo_url + "/{}/devel/".format(chroot_id),
            "name": "Copr buildroot",
        })

    def get_additional_repo_views(repos_list):
        repos = []
        for repo in repos_list:
            params = parse_repo_params(repo)
            repo_view = {
                "id": generate_repo_name(repo),
                "baseurl": pre_process_repo_url(chroot_id, repo),
                "name": "Additional repo " + generate_repo_name(repo),
            }
            repo_view.update(params)
            repos.append(repo_view)
        return repos

    repos.extend(get_additional_repo_views(copr.repos_list))
    repos.extend(get_additional_repo_views(chroot.repos_list))

    return {
        'project_id': copr.repo_id,
        'additional_packages': packages.split(),
        'repos': repos,
        'chroot': chroot_id,
        'use_bootstrap_container': copr.use_bootstrap_container,
        'with_opts': chroot.with_opts.split(),
        'without_opts': chroot.without_opts.split(),
    }


def generate_additional_repos(copr_chroot):
    base_repo = "copr://{}".format(copr_chroot.copr.full_name)
    repos = [base_repo] + copr_chroot.repos_list + copr_chroot.copr.repos_list
    if not copr_chroot.copr.auto_createrepo:
        repos.append("copr://{}/devel".format(copr_chroot.copr.full_name))
    return repos


def trim_git_url(url):
    if not url:
        return None

    return re.sub(r'(\.git)?/*$', '', url)


def get_parsed_git_url(url):
    if not url:
        return False

    url = trim_git_url(url)
    return urlparse(url)


def get_copr_repo_id(copr_dir):
    """
    We cannot really switch to the new
    copr:{hostname}:{owner}:{project} format yet, because it is implemented in
    dnf-plugins-core-3.x which is only on F29+

    Since the F29+ plugin is able to work with both old and new formats, we can
    safely stay with the old one until F28 is still supported. Once it goes EOL,
    we can migrate to the new format.

    New format is:

        return "copr:{0}:{1}:{2}".format(app.config["PUBLIC_COPR_HOSTNAME"].split(":")[0],
                                         copr_dir.copr.owner_name.replace("@", "group_"),
                                         copr_dir.name)

    """
    return copr_dir.repo_id
