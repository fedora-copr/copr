import json
import flask
import wtforms
import sqlalchemy
import inspect
from functools import wraps
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.exceptions import HTTPException, NotFound, GatewayTimeout
from coprs import app
from coprs.exceptions import (
    AccessRestricted,
    ActionInProgressException,
    CoprHttpException,
    InsufficientStorage,
    ObjectNotFound,
)
from coprs.logic.complex_logic import ComplexLogic


apiv3_ns = flask.Blueprint("apiv3_ns", __name__, url_prefix="/api_3")


# HTTP methods
GET = ["GET"]
POST = ["POST"]
PUT = ["POST", "PUT"]
DELETE = ["POST", "DELETE"]


def query_params():
    def query_params_decorator(f):
        @wraps(f)
        def query_params_wrapper(*args, **kwargs):
            sig = inspect.signature(f)
            params = [x for x in sig.parameters]
            params = list(set(params) - {"args", "kwargs"})
            for arg in params:
                if arg not in flask.request.args:
                    # If parameter has a default value, it is not required
                    if sig.parameters[arg].default == sig.parameters[arg].empty:
                        raise CoprHttpException("Missing argument {}".format(arg))
                kwargs[arg] = flask.request.args.get(arg)
            return f(*args, **kwargs)
        return query_params_wrapper
    return query_params_decorator


def pagination():
    def pagination_decorator(f):
        @wraps(f)
        def pagination_wrapper(*args, **kwargs):
            form = PaginationForm(flask.request.args)
            if not form.validate():
                raise CoprHttpException(form.errors)
            kwargs.update(form.data)
            return f(*args, **kwargs)
        return pagination_wrapper
    return pagination_decorator


def file_upload():
    def file_upload_decorator(f):
        @wraps(f)
        def file_upload_wrapper(*args, **kwargs):
            if "json" in flask.request.files:
                data = json.loads(flask.request.files["json"].read()) or {}
                tuples = [(k, v) for k, v in data.items()]
                flask.request.form = ImmutableMultiDict(tuples)
            return f(*args, **kwargs)
        return file_upload_wrapper
    return file_upload_decorator


class PaginationForm(wtforms.Form):
    limit = wtforms.IntegerField("Limit", validators=[wtforms.validators.Optional()])
    offset = wtforms.IntegerField("Offset", validators=[wtforms.validators.Optional()])
    order = wtforms.StringField("Order by", validators=[wtforms.validators.Optional()])
    order_type = wtforms.SelectField("Order type", validators=[wtforms.validators.Optional()],
                                     choices=[("ASC", "ASC"), ("DESC", "DESC")], default="ASC")


def get_copr(ownername=None, projectname=None):
    request = flask.request
    ownername = ownername or request.form.get("ownername") or request.json["ownername"]
    projectname = projectname or request.form.get("projectname") or request.json["projectname"]
    return ComplexLogic.get_copr_by_owner_safe(ownername, projectname)


class Paginator(object):
    LIMIT = None
    OFFSET = 0
    ORDER = "id"

    def __init__(self, query, model, limit=None, offset=None, order=None, order_type=None, **kwargs):
        self.query = query
        self.model = model
        self.limit = limit or self.LIMIT
        self.offset = offset or self.OFFSET
        self.order = order or self.ORDER
        self.order_type = order_type
        if not self.order_type:
            # desc/asc unspecified, use some guessed defaults
            if self.order == 'id':
                self.order_type = 'DESC'
            if self.order == 'name':
                self.order_type = 'ASC'


    def get(self):
        if not hasattr(self.model, self.order):
            raise CoprHttpException("Can order by: {}".format(self.order))

        order_fun = (lambda x: x)
        if self.order_type == 'ASC':
            order_fun = sqlalchemy.asc
        elif self.order_type == 'DESC':
            order_fun = sqlalchemy.desc

        return self.query.order_by(order_fun(self.order)).limit(self.limit).offset(self.offset)

    @property
    def meta(self):
        return {k: getattr(self, k) for k in ["limit", "offset", "order", "order_type"]}

    def map(self, fun):
        return [fun(x) for x in self.get()]

    def to_dict(self):
        return [x.to_dict() for x in self.get()]


class ListPaginator(Paginator):
    """
    The normal `Paginator` class works with a SQLAlchemy query object and
    therefore can do limits and ordering on database level, which is ideal.
    However, in some special cases, we already have a list of objects fetched
    from database and need to adjust it based on user pagination preferences,
    hence this special case of `Paginator` class.

    It isn't efficient, it isn't pretty. Please use `Paginator` if you can.
    """
    def get(self):
        objects = self.query
        reverse = self.order_type != "ASC"

        if not hasattr(self.model, self.order):
            raise CoprHttpException("Can order by: {}".format(self.order))

        if self.order:
            objects.sort(key=lambda x: getattr(x, self.order), reverse=reverse)

        limit = None
        if self.limit:
            limit = self.offset + self.limit

        return objects[self.offset : limit]


def editable_copr(f):
    @wraps(f)
    def wrapper(ownername, projectname, **kwargs):
        copr = get_copr(ownername, projectname)
        if not flask.g.user.can_edit(copr):
            raise AccessRestricted(
                "User '{0}' can not see permissions for project '{1}' "\
                "(missing admin rights)".format(
                    flask.g.user.name,
                    '/'.join([ownername, projectname])
                )
            )
        return f(copr, **kwargs)
    return wrapper
