from __future__ import with_statement

import os
import flask

from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.openid import OpenID

app = flask.Flask(__name__)

if 'COPRS_ENVIRON_PRODUCTION' in os.environ:
    app.config.from_object('coprs.config.ProductionConfig')
elif 'COPRS_ENVIRON_UNITTEST' in os.environ:
    app.config.from_object('coprs.config.UnitTestConfig')
else:
    app.config.from_object('coprs.config.DevelopmentConfig')

oid = OpenID(app, app.config['OPENID_STORE'])
db = SQLAlchemy(app)

@app.before_request
def lookup_current_user():
    flask.g.user = None
    if 'openid' in flask.session:
        flask.g.user = models.User.query.filter(models.User.openid_name == flask.session['openid']).first()


@app.errorhandler(404)
def page_not_found(message):
    return flask.render_template('404.html', message = message), 404

import coprs.models
import coprs.filters

from coprs.views.coprs_ns import builds # this uses coprs_ns blueprint
from coprs.views.coprs_ns import general
from coprs.views import misc
from coprs.views import waiting_builds

app.register_blueprint(general.coprs_ns)
app.register_blueprint(misc.misc)
app.register_blueprint(waiting_builds.waiting_builds_ns)

@app.route("/")
def start():
    return general.coprs_show()
