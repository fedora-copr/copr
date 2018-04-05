import flask
import wtforms
import sqlalchemy
from coprs.exceptions import CoprHttpException
from coprs.logic.complex_logic import ComplexLogic


apiv3_ns = flask.Blueprint("apiv3_ns", __name__, url_prefix="/api_3")


@apiv3_ns.errorhandler(CoprHttpException)
def handle_api_errors(error):
    response = flask.jsonify(error=error.message)
    response.status_code = error.code
    return response


def optional_params(form_class):
    def optional_params_decorator(f):
        def wrapper(*args, **kwargs):
            form = form_class(flask.request.args)
            if not form.validate():
                raise CoprHttpException(form.errors)

            unexpected = set(flask.request.args) - form.data.keys()
            if unexpected:
                raise CoprHttpException("Unexpected arguments: {}".format(", ".join(unexpected)))

            kwargs.update(form.data)

            return f(*args, **kwargs)
        return wrapper
    return optional_params_decorator


class BaseListForm(wtforms.Form):
    limit = wtforms.IntegerField("Limit", validators=[wtforms.validators.Optional()])
    offset = wtforms.IntegerField("Offset", validators=[wtforms.validators.Optional()])
    order = wtforms.StringField("Order by", validators=[wtforms.validators.Optional()])
    order_type = wtforms.SelectField("Order type", validators=[wtforms.validators.Optional()],
                                     choices=[("ASC", "ASC"), ("DESC", "DESC")], default="ASC")


def get_copr():
    ownername = flask.request.args.get("ownername") or flask.request.form["ownername"]
    projectname = flask.request.args.get("projectname") or flask.request.form["projectname"]
    return ComplexLogic.get_copr_by_owner_safe(ownername, projectname)


class Paginator(object):
    LIMIT = 100
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
        return self.query.order_by(order_fun(order_col)).limit(self.limit).offset(self.offset)

    @property
    def meta(self):
        return {k: getattr(self, k) for k in ["limit", "offset", "order", "order_type"]}

    def map(self, fun):
        return [fun(x) for x in self.get()]

    def to_dict(self):
        return [x.to_dict() for x in self.get()]
