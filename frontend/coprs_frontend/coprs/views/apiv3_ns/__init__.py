import json
import flask
import wtforms
import sqlalchemy
import inspect
from functools import wraps
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.exceptions import HTTPException, NotFound, GatewayTimeout
from sqlalchemy.orm.attributes import InstrumentedAttribute
from coprs import app
from coprs.exceptions import (
    AccessRestricted,
    ActionInProgressException,
    CoprHttpException,
    InsufficientStorage,
    ObjectNotFound,
    BadRequest,
)
from coprs.logic.complex_logic import ComplexLogic
from coprs.helpers import streamed_json


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
                    # If parameter is present in the URL path, we can use its
                    # value instead of failing that it is missing in query
                    # parameters, e.g. let's have a view decorated with these
                    # two routes:
                    #     @foo_ns.route("/foo/bar/<int:build>/<chroot>")
                    #     @foo_ns.route("/foo/bar") accepting ?build=X&chroot=Y
                    #     @query_params()
                    # Then we need the following condition to get the first
                    # route working
                    if arg in flask.request.view_args:
                        continue

                    # If parameter has a default value, it is not required
                    if sig.parameters[arg].default == sig.parameters[arg].empty:
                        raise BadRequest("Missing argument {}".format(arg))
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
        return self.paginate_query(self.query)

    def paginate_query(self, query):
        """
        Return `self.query` with all pagination parameters (limit, offset,
        order) but do not run it.
        """
        order_attr = getattr(self.model, self.order, None)
        if not order_attr:
            msg = "Cannot order by {}, {} doesn't have such property".format(
                self.order, self.model.__tablename__)
            raise CoprHttpException(msg)

        # This will happen when trying to sort by a property instead of
        # a real database column
        if not isinstance(order_attr, InstrumentedAttribute):
            raise CoprHttpException("Cannot order by {}".format(self.order))

        order_fun = (lambda x: x)
        if self.order_type == 'ASC':
            order_fun = sqlalchemy.asc
        elif self.order_type == 'DESC':
            order_fun = sqlalchemy.desc

        return (query.order_by(order_fun(order_attr))
                .limit(self.limit)
                .offset(self.offset))

    @property
    def meta(self):
        return {k: getattr(self, k) for k in ["limit", "offset", "order", "order_type"]}

    def map(self, fun):
        return [fun(x) for x in self.get()]

    def to_dict(self):
        return [x.to_dict() for x in self.get()]


class SubqueryPaginator(Paginator):
    """
    Selecting rows with large offsets (400k+) is slower (~10 times) than
    offset=0. There is not many options to get around it. To mitigate the
    slowdown at least a little (~10%), we can filter, offset, and limit within
    a subquery and then base the full-query on the subquery results.
    """
    def __init__(self, query, subquery, *args, **kwargs):
        super().__init__(query, *args, **kwargs)
        self.pk = getattr(self.model, "id")
        self.subquery = subquery.with_entities(self.pk)

    def get(self):
        subquery = self.paginate_query(self.subquery).subquery()
        query = self.query.filter(self.pk.in_(subquery))
        return query.all()


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
            msg = "Cannot order by {}, {} doesn't have such property".format(
                self.order, self.model.__tablename__)
            raise CoprHttpException(msg)

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


def set_defaults(formdata, form_class):
    """
    Take a `formdata` which can be `flask.request.form` or an output from
    `get_form_compatible_data`, and `form_class` (not instance). This function
    then goes through all fields defaults and update the `formdata` if those
    fields weren't set from a user.

    I don't understand why this is necessary, I would expect a `form.foo.data`
    to return the request value or `default` but it doesn't seem to work like
    that. See the `wtforms.fields.Field` documentation:

    > default – The default value to assign to the field, if no form or object
    >           input is provided. May be a callable.

    The **if no form or object input is provided** is really unexpected. We
    always initialize our forms with request data, i.e. the defaults are never
    used? IMHO a more reasonable approach would be doing this per field.

    A field `default` value seems to be used only when rendering an empty form,
    which is good enough for rendering an empty form into HTML (even though it
    forces us to render all fields, which IMHO shouldn't be necessary). This
    doesn't work at all for API where users send only a subset of form fields
    and expect reasonable defaults for the rest.
    """
    form = form_class(ImmutableMultiDict())
    for field in form:
        if field.default is None:
            continue
        if field.name in formdata.keys():
            continue
        formdata[field.name] = field.default


def streamed_json_array_response(array_or_generator, message, field="data"):
    """
    Helper response to stream large JSON API arrays (ARRAY_OR_GENERATOR).  We
    keep the layout of the output like::

        {
            "output": "ok",
            "message: MESSAGE,
            "<FIELD>": [ ITEM, ITEM, ...,]
        }

    .. as it is expected by clients.  We iterate continuously over the array
    items (or fetch from generator), so we don't have to keep the large dataset
    in memory (or wait till it is fully fetched from DB).
    """
    start_string = (
        '{{'
        '"output": "ok",'
        '"message": {message},'
        '{field}: [\n'
    ).format(message=json.dumps(message),
             field=json.dumps(field))
    return streamed_json(array_or_generator, start_string, "]}")


def str_to_list(value):
    """
    We have a lot of module attributes that are stored as space-separeted
    strings, their default value is `None` and we want to return them as lists.
    It's tiresome to always check if the value is not `None` before splitting.
    """
    return (value or "").split()


def reset_to_defaults(obj, form, rename_fields=None, more_fields=None):
    """
    If the `form` contains a `reset` with a list of attributes that user wishes
    to reset, set such values to their respective defaults. We find out the
    default value from `obj`, which should be any database model.

    Sometimes an attribute within the API schema can have a different name than
    its model counterpart. For such cases this method takes an `rename_fields`,
    function, see e.g. `apiv3_project_chroots.rename_fields`.

    Use `more_fields` to specify a message saying where a user can find all the
    possible attribute names
    """
    reset = getattr(form, "reset_fields")
    if not reset or not reset.data:
        return
    fields = str_to_list(reset.data)

    # Some fields may have different name in the API schema than their
    # respective attributes in the database models.
    if rename_fields:
        fields = rename_fields(dict.fromkeys(fields)).keys()

    for field in fields:
        try:
            default = getattr(obj.__class__, field).default
            value = default.arg if default else None
            setattr(obj, field, value)
        except AttributeError as ex:
            msg = "Trying to reset an invalid attribute: {0}".format(field)
            if more_fields:
                msg += "\n{0}".format(more_fields)
            raise BadRequest(msg) from ex
