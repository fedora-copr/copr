import datetime
import functools
import random
import string

import flask

from flask.ext.openid import OpenID

from coprs import app
from coprs import config
from coprs import db
from coprs import models
from coprs import oid

misc = flask.Blueprint('misc', __name__)

def generate_api_token(size=30):
    """ Generate a random string used as token to access the API
    remotely.

    :kwarg: size, the size of the token to generate, defaults to 30
        chars.
    :return: a string, the API token for the user.

    """
    return ''.join(random.choice(string.ascii_lowercase) for x in range(size))


@misc.route('/login/', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if flask.g.user is not None:
        return flask.redirect(oid.get_next_url())
    if flask.request.method == 'POST':
        fasusername = flask.request.form.get('fasuname')
        if fasusername and ((app.config['USE_ALLOWED_USERS'] \
            and fasusername in app.config['ALLOWED_USERS']) \
            or not app.config['USE_ALLOWED_USERS']):
            return oid.try_login('http://{0}.id.fedoraproject.org/'.format(fasusername), ask_for = ["email"])
        else:
            return flask.render_template('login.html',
                            error='User "{0}" is not allowed'.format(
                            fasusername))
    return flask.render_template('login.html',
                                 next=oid.get_next_url(),
                                 error=oid.fetch_error())

@oid.after_login
def create_or_login(resp):
    flask.session['openid'] = resp.identity_url
    user = models.User.query.filter(
        models.User.openid_name == resp.identity_url).first()
    if not user: # create if not created already
        expiration_date_token = datetime.date.today() \
            + datetime.timedelta(days=30)
        user = models.User(openid_name = resp.identity_url, mail = resp.email,
            api_token = generate_api_token(app.config['API_TOKEN_LENGTH']),
            api_token_expiration = expiration_date_token)
        db.session.add(user)
        db.session.commit()
    flask.flash(u'Welcome, {0}'.format(user.name))
    flask.g.user = user
    return flask.redirect(oid.get_next_url())


@misc.route('/logout/')
def logout():
    flask.session.pop('openid', None)
    flask.flash(u'You were signed out')
    return flask.redirect(oid.get_next_url())


def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = flask.request.form.get('token')
        username = flask.request.form.get('username')
        token_auth = False
        if token and username:
            user = models.User.query.filter(
                models.User.openid_name == models.User.openidize_name(username)
                ).first()
            if user \
                and user.api_token == token \
                and user.api_token_expiration >= datetime.date.today():
                token_auth = True
                flask.g.user = user
        if not token_auth and flask.g.user is None:
            return flask.redirect(flask.url_for('misc.login',
                next = flask.request.url))
        return f(*args, **kwargs)
    return decorated_function


# backend authentication
def backend_authenticated(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth = flask.request.authorization
        if not auth or auth.password != app.config['BACKEND_PASSWORD']:
            return 'You have to provide the correct password', 401
        return f(*args, **kwargs)
    return decorated_function


@misc.route('/api/')
def api():
    return flask.render_template('api.html',
                                 user=flask.g.user)


@misc.route('/api/new/', methods = ["GET", "POST"])
@login_required
def api_new_token():
    user = flask.g.user
    user.api_token = generate_api_token(app.config['API_TOKEN_LENGTH'])
    user.api_token_expiration = datetime.date.today() \
        + datetime.timedelta(days=30)
    db.session.add(user)
    db.session.commit()
    flask.g.user = user
    return flask.redirect(flask.url_for('misc.api'))
