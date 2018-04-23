import flask
import wtforms
import sqlalchemy
import inspect
from functools import wraps
from coprs.exceptions import CoprHttpException
from coprs.logic.complex_logic import ComplexLogic


apiv3_ns = flask.Blueprint("apiv3_ns", __name__, url_prefix="/api_3")


@apiv3_ns.errorhandler(CoprHttpException)
def handle_api_errors(error):
    response = flask.jsonify(error=error.message)
    response.status_code = error.code
    return response


def query_params():
    def query_params_decorator(f):
        @wraps(f)
        def query_params_wrapper(*args, **kwargs):
            params = [x for x in inspect.signature(f).parameters]
            params = list(set(params) - {"args", "kwargs"})
            for arg in params:
                if arg not in flask.request.args:
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


class PaginationForm(wtforms.Form):
    limit = wtforms.IntegerField("Limit", validators=[wtforms.validators.Optional()])
    offset = wtforms.IntegerField("Offset", validators=[wtforms.validators.Optional()])
    order = wtforms.StringField("Order by", validators=[wtforms.validators.Optional()])
    order_type = wtforms.SelectField("Order type", validators=[wtforms.validators.Optional()],
                                     choices=[("ASC", "ASC"), ("DESC", "DESC")], default="ASC")


def get_copr(ownername=None, projectname=None):
    request = flask.request
    ownername = ownername or request.args.get("ownername") or request.form.get("ownername") or request.json["ownername"]
    projectname = projectname or request.args.get("projectname") or request.form.get("projectname") or request.json["projectname"]
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
        order_col = getattr(self.model, self.order)
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
