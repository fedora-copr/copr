import functools

import flask

from flask.ext.openid import OpenID

from coprs import db
from coprs import models
from coprs import oid

misc = flask.Blueprint('misc', __name__)

@misc.route('/login/', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    if flask.g.user is not None:
        return flask.redirect(oid.get_next_url())
    if flask.request.method == 'POST':
        fasusername = flask.request.form.get('fasuname')
        if fasusername:
            return oid.try_login('http://{0}.id.fedoraproject.org/'.format(fasusername))
        openid = flask.request.form.get('openid')
        if openid:
            return oid.try_login(openid)
    return flask.render_template('login.html',
                                 next=oid.get_next_url(),
                                 error=oid.fetch_error())


@oid.after_login
def create_or_login(resp):
    flask.session['openid'] = resp.identity_url
    user = models.User.query.filter(models.User.openid_name == resp.identity_url).first()
    if not user: # create if not created already
        user = models.User(openid_name = resp.identity_url)
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
        if flask.g.user is None:
            return flask.redirect(flask.url_for('misc.login', next = flask.request.url))
        return f(*args, **kwargs)
    return decorated_function
