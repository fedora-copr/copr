"""
Copr Frontend helper classes, functions, methods, constants, etc.
"""

import math
import random
import string
import json
from os.path import normpath
import posixpath
import re
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

import html5_parser

import flask
from flask import url_for
from redis import StrictRedis
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql.sqltypes import String, DateTime, NullType

from werkzeug.urls import url_encode

from copr_common.enums import EnumType, StatusEnum
# TODO: don't import BuildSourceEnum from helpers, use copr_common.enum instead
from copr_common.enums import BuildSourceEnum # pylint: disable=unused-import
from copr_common.rpm import splitFilename
from coprs import app


def generate_api_token(size=30):
    """ Generate a random string used as token to access the API
    remotely.

    :kwarg: size, the size of the token to generate, defaults to 30
        chars.
    :return: a string, the API token for the user.
    """
    return ''.join(random.choice(string.ascii_lowercase) for x in range(size))


FINISHED_STATES = ["succeeded", "forked", "canceled", "skipped", "failed"]
FINISHED_STATUSES = [StatusEnum(s) for s in FINISHED_STATES]


class WorkList:
    """
    WorkList (TODO list) abstraction

    This is useful if we want to process some dynamically changing TODO list
    (directed graph traversal) and we want to make sure that each task is
    processed only once.  E.g. to check all (even transitive) dependencies:

        wl = WorkList(["dep A", "dep B"]
        while not wl.empty:
            dep = wl.pop()
            if not dep_available(dep):
                print(dep + " not found")  # problem found
                continue
            for dep in get_2nd_level_deps(dep):
                wl.schedule(dep)

    Note that (a) each task, even if it is scheduled multiple times, is
    processed only once - so subsequent schedule() calls are no-ops, (b) tasks
    can be scheduled while the WorkList is being processed and (c) tasks need to
    be hashable objects.

    Implementation inspired by Predator project:
    http://www.fit.vutbr.cz/research/groups/verifit/tools/predator/api/classWorkList.html
    """
    def __init__(self, initial_tasks):
        self._tasks = []
        self._seen = set()
        for task in initial_tasks:
            self.schedule(task)

    def schedule(self, task):
        """ Add task to queue, if it is not already there or processed """
        if task in self._seen:
            return False
        self._tasks.insert(0, task)
        self._seen.add(task)
        return True

    @property
    def empty(self):
        """ True if there's nothing to do """
        return not bool(len(self._tasks))

    def pop(self):
        """ Get task (the oldest one) """
        return self._tasks.pop()


class CounterStatType(object):
    # When a .repo file is generated on the frontend.
    # It is displayed in the "Repo Download" column on project overview pages.
    REPO_DL = "repo_dl"

    # When an RPM or SRPM file is downloaded directly from the backend
    # or from Amazon AWS CDN.
    # It is displayed in the "Architectures" column on project overview pages.
    CHROOT_RPMS_DL = "chroot_rpms_dl"

    # When a repodata/repomd.xml RPM or SRPM file is downloaded directly from
    # the backend or from Amazon AWS CDN.
    # We are counting but not using this information anywhere.
    CHROOT_REPO_MD_DL = "chroot_repo_metadata_dl"

    # This should equal to the sum of all `CHROOT_RPMS_DL` stats within
    # a project. It is a redundant information to be stored, since it can be
    # calculated. But our `model.CounterStat` design isn't friendly for querying
    # based on owner/project.
    # We are counting but not using this information anywhere.
    PROJECT_RPMS_DL = "project_rpms_dl"


def get_stat_name(stat_type, copr_dir=None, copr_chroot=None,
                  name_release=None, key_string=None):
    """
    Generate a `models.CounterStat.name` value based on various optional
    parameters. Only a subset of parameters needs to be set based on the context
    and `stat_type`.

    This method is too complicated and messy, we should either minimize the
    number of input parameters if possible, or turn this into a class with
    methods for each `stat_type` or use-case.
    """

    # TODO These are way too complicated
    # We should get rid of the redis syntax (hset::)
    #
    # We should not start the value with `stat_type` because we already have
    # `CounterStat.counter_type` for that.
    #
    # We should probably add `CounterStat.copr_id` to remove `copr_user`
    # and `copr_project` from the strings
    # pylint: disable=invalid-name
    REPO_DL_STAT_FMT = "repo_dl_stat::{copr_user}@{copr_project_name}:{copr_name_release}"
    CHROOT_REPO_MD_DL_STAT_FMT = "chroot_repo_metadata_dl_stat:hset::{copr_user}@{copr_project_name}:{copr_chroot}"
    CHROOT_RPMS_DL_STAT_FMT = "chroot_rpms_dl_stat:hset::{copr_user}@{copr_project_name}:{copr_chroot}"
    PROJECT_RPMS_DL_STAT_FMT = "project_rpms_dl_stat:hset::{copr_user}@{copr_project_name}"

    stat_fmt = {
        CounterStatType.REPO_DL: REPO_DL_STAT_FMT,
        CounterStatType.CHROOT_REPO_MD_DL: CHROOT_REPO_MD_DL_STAT_FMT,
        CounterStatType.CHROOT_RPMS_DL: CHROOT_RPMS_DL_STAT_FMT,
        CounterStatType.PROJECT_RPMS_DL: PROJECT_RPMS_DL_STAT_FMT,
    }.get(stat_type)

    if not stat_fmt:
        raise ValueError("Unexpected stat_type")

    kwargs = {}
    if name_release:
        kwargs["copr_name_release"] = name_release

    if copr_dir:
        kwargs.update({
            "copr_user": copr_dir.copr.owner_name,
            "copr_project_name": copr_dir.copr.name,
        })

    if copr_chroot:
        kwargs.update({
            "copr_user": copr_chroot.copr.owner_name,
            "copr_project_name": copr_chroot.copr.name,
            "copr_chroot": copr_chroot.name,
        })

    # The key strings come from backend hitcounter scripts, e.g.
    # 'project_rpms_dl_stat|jvanek|java17'
    if key_string:
        keys = key_string.split("|")
        kwargs.update({
            "copr_user": keys[0],
            "copr_project_name": keys[1],
        })

    # Also from backend hitcounter scripts, e.g.
    # 'chroot_repo_metadata_dl_stat|jose_exposito|touchegg|fedora-35-x86_64'
    # 'chroot_rpms_dl_stat|packit|psss-tmt-896|fedora-rawhide-x86_64'
    if key_string and stat_type in [CounterStatType.CHROOT_RPMS_DL,
                                    CounterStatType.CHROOT_REPO_MD_DL]:
        keys = key_string.split("|")
        kwargs["copr_chroot"] = keys[2]

    return stat_fmt.format(**kwargs)


class PermissionEnum(metaclass=EnumType):
    # The text form is part of APIv3!
    vals = {"nothing": 0, "request": 1, "approved": 2}

    @classmethod
    def choices_list(cls, without=-1):
        return [(n, k) for k, n in cls.vals.items() if n != without]


class ChrootDeletionStatus(metaclass=EnumType):
    """
    When a chroot is marked as EOL or when it is unclicked from a project,
    it goes through several stages before its data is finally deleted.
    Each `models.CoprChroot` is in one of the following states.
    """
    # pylint: disable=too-few-public-methods
    vals = {
        # The chroot is enabled within its project and its data wasn't deleted
        # or isn't going to be deleted in the future
        "active": 0,

        # Temporarily (or even permanently) deactivated chroot. It is not
        # marked as EOL and its data is never going to be deleted.
        "deactivated": 1,

        # There are multiple possible scenarios for chroots in this state:
        # 1) The standard preservation period is not over yet. Its length
        #    differs on whether the chroot is EOL or was unclicked from
        #    a project but the meaning is same for both cases
        #
        # 2) If the chroot is EOL and we wasn't able to send a notification
        #    about it.
        #
        # 3) Any other constraint that disallows the chroot to be deleted yet.
        #    At this moment there shouldn't be any.
        "preserved": 2,

        # The standard preservation period is gone and there are no blockers
        # to safely delete data from this chroot
        "expired": 3,

        # The data was already deleted. This includes a case when we attempted
        # to delete the data and the backend action failed for some reason. From
        # frontend's perspective, it doesn't matter.
        "deleted": 4,
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
        self.per_page = per_page_override or app.config["ITEMS_PER_PAGE"]
        self.urls_count = urls_count_override or app.config["PAGES_URLS_COUNT"]
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


def generate_repo_url(mock_chroot, url, arch=None):
    """ Generates url with build results for .repo file.
    No checks if copr or mock_chroot exists.
    """
    os_version = mock_chroot.os_version

    if mock_chroot.os_release == "fedora":
        os_version = "$releasever"

    if mock_chroot.os_release == "opensuse-leap":
        os_version = "$releasever"

    if mock_chroot.os_release == "mageia":
        if mock_chroot.os_version != "cauldron":
            os_version = "$releasever"

    url = posixpath.join(
        url, "{0}-{1}-{2}/".format(mock_chroot.os_release,
                                   os_version, arch or '$basearch'))

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
    def __init__(self, config, db=0):
        self.host = config.get("REDIS_HOST", "127.0.0.1")
        self.port = int(config.get("REDIS_PORT", "6379"))
        self.db = db

    def get_connection(self):
        return StrictRedis(host=self.host, port=self.port, db=self.db)


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


def owner_url(owner):
    """
    For a given `owner` object, which may be either `models.User` or `models.Group`,
    return an URL to its _profile_ page.
    """
    # We can't check whether owner is instance of `models.Group` because once
    # we include models from helpers, we get circular imports
    if hasattr(owner, "at_name"):
        return url_for("groups_ns.list_projects_by_group", group_name=owner.name)
    return url_for("coprs_ns.coprs_by_user", username=owner.username)


def url_for_copr_view(view, group_view, copr, **kwargs):
    if copr.is_a_group_project:
        return url_for(group_view, group_name=copr.group.name, coprname=copr.name, **kwargs)
    else:
        return url_for(view, username=copr.user.name, coprname=copr.name, **kwargs)


def url_for_copr_builds(copr):
    return copr_url("coprs_ns.copr_builds", copr)


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


def is_copr_repo(repo_url):
    return copr_repo_fullname(repo_url) is not None


def copr_repo_fullname(repo_url):
    parsed_url = urlparse(repo_url)
    query = parse_qs(parsed_url.query)
    if parsed_url.scheme != "copr":
        return None
    return parsed_url.netloc + parsed_url.path


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


def trim_git_url(url):
    if not url:
        return None

    return re.sub(r'(\.git)?/*$', '', url)


def get_parsed_git_url(url):
    if not url:
        return False

    url = trim_git_url(url)
    return urlparse(url)


class SubdirMatch(object):
    def __init__(self, subdir):
        if not subdir:
            self.subdir = '.'
        else:
            self.subdir = normpath(subdir).strip('/')

    def match(self, path):
        if not path: # shouldn't happen
            return False

        changed = normpath(path).strip('/')
        if changed == '.':
            return False # shouldn't happen!

        if self.subdir == '.':
            return True

        return changed.startswith(self.subdir + '/')


def pagure_html_diff_changed(html_string):
    parsed = html5_parser.parse(str(html_string))
    elements = parsed.xpath(
        "//section[contains(@class, 'commit_diff')]"
        "//div[contains(@class, 'card-header')]"
        "//a[contains(@class, 'font-weight-bold')]"
        "/text()")

    return set([str(x) for x in elements])


def raw_commit_changes(text):
    changes = set()
    for line in text.split('\n'):
        match = re.search(r'^(\+\+\+|---) [ab]/(.*)$', line)
        if match:
            changes.add(str(match.group(2)))
        match = re.search(r'^diff --git a/(.*) b/(.*)$', line)
        if match:
            changes.add(str(match.group(1)))
            changes.add(str(match.group(2)))
            print(changes)

    return changes


def pluralize(what: str, items: list, be_suffix: bool = False) -> str:
    """
    By giving ``what`` string (e.g. "build") and ``items`` array, return string
    in either of those formats:
    - "builds 1, 2, 3, and 4[ are]"
    - "builds 1, 2, and others[ are]"
    - "builds 1 and 2[ are]"
    - "build 31[ is]"
    """
    if len(items) > 1:
        return "{what}s {list}{comma} and {last}{be_suffix}".format(
            what=what,
            list=', '.join(str(item) for item in items[:-1]),
            comma=',' if len(items) > 2 else "",
            last=str(items[-1]),
            be_suffix=" are" if be_suffix else "",
        )
    return "{} {}{}".format(
        what,
        items[0],
        " is" if be_suffix else ""
    )

def clone_sqlalchemy_instance(instance, ignored=None):
    """
    Clone an object, but skip the primary key.
    """
    new_instance = type(instance)()
    if not ignored:
        ignored = []

    # Copy the normal table columns.
    for col in instance.__table__.columns:
        column = col.name
        if column in ignored:
            continue
        if not hasattr(instance, column):
            # stuff like user_id in _UserPrivate
            continue
        if col.primary_key:
            # the new object needs to have it's own unique primary key
            continue
        if col.foreign_keys:
            # we copy the references instead below
            continue
        setattr(new_instance, column, getattr(instance, column))

    # Load all relationship objects preemptively
    relationships = {}
    for attr, rel in instance.__mapper__.relationships.items():
        if rel.uselist:
            # TODO: support also 1:N, not only N:1
            continue
        relationships[attr] = getattr(instance, attr)

    # Copy the references.  It is better to copy 'new.parent = old.parent'
    # than just 'old.parent_id' because the 'new' object wouldn't have the
    # 'new.parent' object loaded.
    for attr, rel in relationships.items():
        setattr(new_instance, attr, rel)

    return new_instance


def current_url(**kwargs):
    """
    Generate the same url as is currently processed, but define (or replace) the
    arguments in kwargs.
    """
    new_args = {}
    new_args.update(flask.request.args)
    new_args.update(kwargs)
    if not new_args:
        return flask.request.path
    return '{}?{}'.format(flask.request.path, url_encode(new_args))


def parse_fullname(full_name):
    """
    Take a string in a `ownername/projectname` format and return them in a tuple
    `(ownername, projectname)`. If a string without a forward-slash is passed,
    it is considered to be a projectname without ownername.
    """
    if "/" in full_name:
        return full_name.split("/", maxsplit=1)
    return None, full_name


def format_search_string(params):
    """
    Takes a dict of parameters that were specified for searching and return
    them in a formatted, human-readable string.

    {"ownername": "@copr", "projectname": "copr-dev"}
        => "ownername: @copr, projectname: copr-dev"

    {"ownername": "frostyx", "fulltext": "foo"}
        => "ownername: frostyx, foo"
    """
    params_copy = dict(params.copy())
    fulltext = params_copy.pop("fulltext", None)

    params_list = ["{0}: {1}".format(k, v) for k, v in params_copy.items()]
    if not params_list:
        return fulltext

    result = ", ".join(params_list)
    if not fulltext:
        return result
    return ", ".join([result, fulltext])

def db_column_length(column):
    """
    Return the maximum string length for a given database column.
    Call with e.g. `column=models.Package.name`
    """
    return getattr(column, "property").columns[0].type.length


@flask.stream_with_context
def streamed_json(stream, start_string=None, stop_string=None):
    """
    Flask response generator for JSON structures (arrays only for now)
    """

    start_string = start_string or "["
    stop_string = stop_string or "]"

    def _stream():
        yield start_string
        first = True
        for item in stream:
            if first:
                yield json.dumps(item)
                first = False
            else:
                yield ",\n" + json.dumps(item)
        yield stop_string

    def _batched_stream(count=100):
        """
        Don't dump all the JSON items separately, but batch them by COUNT.  This
        makes the upper-level Flask generator logic called less frequently
        increasing the overall throughput.
        """
        output = ""
        counter = 0
        for chunk in _stream():
            counter += 1
            output += chunk
            if counter % count == 0:
                yield output
                output = ""
        yield output

    def _response():
        return app.response_class(
            _batched_stream(),
            mimetype="application/json",
        )

    return _response()


def being_server_admin(user, copr):
    """
    Is Copr maintainer using their special permissions to edit the project?
    """
    if not user:
        return False

    if not user.admin:
        return False

    if user == copr.user:
        return False

    if user.can_edit(copr, ignore_admin=True):
        return False

    return True
