import base64
import datetime
import functools

import flask

from flask.ext.openid import OpenID

from coprs import app
from coprs import config
from coprs import db
from coprs import helpers
from coprs import models
from coprs import oid

@app.before_request
def lookup_current_user():
    flask.g.user = None
    if 'openid' in flask.session:
        flask.g.user = models.User.query.filter(models.User.openid_name==flask.session['openid']).first()

@app.errorhandler(404)
def page_not_found(message):
    return flask.render_template('404.html', message=message), 404


misc = flask.Blueprint('misc', __name__)


@misc.route('/login/', methods=['GET'])
@oid.loginhandler
def login():
    if flask.g.user is not None:
        return flask.redirect(oid.get_next_url())
    else:
        return oid.try_login('https://id.fedoraproject.org/', ask_for=['email', 'timezone'])

@oid.after_login
def create_or_login(resp):
    flask.session['openid'] = resp.identity_url
    fasusername = resp.identity_url.replace('.id.fedoraproject.org/', '').replace('http://', '')
    if fasusername and ((app.config['USE_ALLOWED_USERS'] \
            and fasusername in app.config['ALLOWED_USERS']) \
            or not app.config['USE_ALLOWED_USERS']):
        user = models.User.query.filter(
            models.User.openid_name == resp.identity_url).first()
        if not user: # create if not created already
            expiration_date_token = datetime.date.today() \
                + datetime.timedelta(days=flask.current_app.config['API_TOKEN_EXPIRATION'])
            copr64 = base64.b64encode('copr') + '##'
            user = models.User(openid_name = resp.identity_url, mail = resp.email,
                api_login = copr64 + helpers.generate_api_token(
                    app.config['API_TOKEN_LENGTH'] - len(copr64)),
                api_token = helpers.generate_api_token(app.config['API_TOKEN_LENGTH']),
                api_token_expiration = expiration_date_token)
            db.session.add(user)
            db.session.commit()
        flask.flash(u'Welcome, {0}'.format(user.name))
        flask.g.user = user
        redirect_to = oid.get_next_url()
        if flask.request.url_root == oid.get_next_url():
            return flask.redirect(flask.url_for('coprs_ns.coprs_by_owner', username=user.name))
        return flask.redirect(oid.get_next_url())
    else:
        flask.flash('User "{0}" is not allowed'.format(user.name))
        return flask.redirect(oid.get_next_url())


@misc.route('/logout/')
def logout():
    flask.session.pop('openid', None)
    flask.flash(u'You were signed out')
    return flask.redirect(oid.get_next_url())


def api_login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        username = None
        if 'Authorization' in flask.request.headers:
            base64string = flask.request.headers['Authorization']
            base64string = base64string.split()[1].strip()
            userstring = base64.b64decode(base64string)
            (username, token) = userstring.split(':')
        token_auth = False
        if token and username:
            user = models.User.query.filter(
                models.User.api_login == username).first()
            if user \
                and user.api_token == token \
                and user.api_token_expiration >= datetime.date.today():
                token_auth = True
                flask.g.user = user
        if not token_auth:
            output = {'output': 'notok', 'error': 'Login invalid/expired'}
            jsonout = flask.jsonify(output)
            jsonout.status_code = 500
            return jsonout
        return f(*args, **kwargs)
    return decorated_function


def login_required(role=helpers.RoleEnum('user')):
    def view_wrapper(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if flask.g.user is None:
                return flask.redirect(flask.url_for('misc.login',
                    next = flask.request.url))
            if role == helpers.RoleEnum('admin') and not flask.g.user.admin:
                flask.flash('You are not allowed to access admin section.')
                return flask.redirect(flask.url_for('coprs_ns.coprs_show'))
            return f(*args, **kwargs)
        return decorated_function
    # hack: if login_required is used without params, the "role" parameter
    # is in fact the decorated function, so we need to return
    # the wrapped function, not the wrapper
    # proper solution would be to use login_required() with parentheses
    # everywhere, even if they're empty - TODO
    if callable(role):
        return view_wrapper(role)
    else:
        return view_wrapper


# backend authentication
def backend_authenticated(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth = flask.request.authorization
        if not auth or auth.password != app.config['BACKEND_PASSWORD']:
            return 'You have to provide the correct password', 401
        return f(*args, **kwargs)
    return decorated_function

