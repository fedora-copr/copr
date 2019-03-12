import json
import flask
import wtforms
import sqlalchemy
import inspect
from functools import wraps
from werkzeug.datastructures import ImmutableMultiDict
from coprs import app
from coprs.exceptions import CoprHttpException, ObjectNotFound
from coprs.logic.complex_logic import ComplexLogic


apiv3_ns = flask.Blueprint("apiv3_ns", __name__, url_prefix="/api_3")


# HTTP methods
GET = ["GET"]
POST = ["POST"]
PUT = ["POST", "PUT"]
DELETE = ["POST", "DELETE"]


class APIErrorHandler(object):
    def handle_404(self, error):
        if isinstance(error, ObjectNotFound):
            return self.respond(str(error), 404)
        return self.respond("Such API endpoint doesn't exist", 404)

    def handle_403(self, error):
        return self.handle_xxx(error)

    def handle_400(self, error):
        return self.handle_xxx(error)

    def handle_500(self, error):
        return self.respond("Request wasn't successful, there is probably a bug in the API code.", 500)

    def handle_504(self, error):
        return self.respond("The API request timeouted", 504)

    def handle_xxx(self, error):
        return self.respond(self.message(error), error.code)

    def respond(self, message, code):
        response = flask.jsonify(error=message)
        response.status_code = code
        return response

    def message(self, error):
        if isinstance(error, CoprHttpException):
            return error.message
        if hasattr(error, "description"):
            return error.description
        return str(error)


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
    ORDER_TYPE = "ASC"

    def __init__(self, query, model, limit=None, offset=None, order=None, order_type=None, **kwargs):
        self.query = query
        self.model = model
        self.limit = limit or self.LIMIT
        self.offset = offset or self.OFFSET
        self.order = order or self.ORDER
        self.order_type = order_type or self.ORDER_TYPE

    def get(self):
        if not hasattr(self.model, self.order):
            raise CoprHttpException("Can order by: {}".format(self.order))
        order_col = self.order
        order_fun = sqlalchemy.desc if self.order_type == "DESC" else sqlalchemy.asc
        return self.query.order_by(None).limit(None).offset(None)\
            .order_by(order_fun(order_col)).limit(self.limit).offset(self.offset)

    @property
    def meta(self):
        return {k: getattr(self, k) for k in ["limit", "offset", "order", "order_type"]}

    def map(self, fun):
        return [fun(x) for x in self.get()]

    def to_dict(self):
        return [x.to_dict() for x in self.get()]
