from __future__ import with_statement

import os
import flask

from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager
from flask_openid import OpenID
from flask_whooshee import Whooshee
from openid_teams.teams import TeamsResponse

from coprs.redis_session import RedisSessionInterface

app = flask.Flask(__name__)
if "COPRS_ENVIRON_PRODUCTION" in os.environ:
    app.config.from_object("coprs.config.ProductionConfig")
elif "COPRS_ENVIRON_UNITTEST" in os.environ:
    app.config.from_object("coprs.config.UnitTestConfig")
else:
    app.config.from_object("coprs.config.DevelopmentConfig")
if os.environ.get("COPR_CONFIG"):
    app.config.from_envvar("COPR_CONFIG")
else:
    app.config.from_pyfile("/etc/copr/copr.conf", silent=True)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

oid = OpenID(
    app, app.config["OPENID_STORE"],
    safe_roots=[],
    extension_responses=[TeamsResponse]
)

db = SQLAlchemy(app)

@contextmanager
def db_session_scope():
    """Provide a transactional scope around a series of operations."""
    session = db.session
    try:
        yield session
        session.commit()
    except Exception as err:
        session.rollback()
        raise

whooshee = Whooshee(app)


import coprs.filters
import coprs.log
from coprs.log import setup_log
import coprs.models
import coprs.whoosheers

from coprs.helpers import RedisConnectionProvider
rcp = RedisConnectionProvider(config=app.config)
app.session_interface = RedisSessionInterface(rcp.get_connection())

from coprs.views import admin_ns
from coprs.views.admin_ns import admin_general
from coprs.views import api_ns
from coprs.views.api_ns import api_general
from coprs.views import apiv3_ns
from coprs.views.apiv3_ns import (apiv3_general, apiv3_builds, apiv3_packages, apiv3_projects, apiv3_project_chroots,
                                  apiv3_modules, apiv3_build_chroots)
from coprs.views import coprs_ns
from coprs.views.coprs_ns import coprs_builds
from coprs.views.coprs_ns import coprs_general
from coprs.views.coprs_ns import coprs_chroots
from coprs.views.coprs_ns import coprs_packages
from coprs.views import backend_ns
from coprs.views.backend_ns import backend_general
from coprs.views import misc
from coprs.views import status_ns
from coprs.views.status_ns import status_general
from coprs.views import recent_ns
from coprs.views.recent_ns import recent_general
from coprs.views.stats_ns import stats_receiver
from coprs.views import tmp_ns
from coprs.views.tmp_ns import tmp_general
from coprs.views.groups_ns import groups_ns
from coprs.views.groups_ns import groups_general
from coprs.views.user_ns import user_ns
from coprs.views.user_ns import user_general
from coprs.views.webhooks_ns import webhooks_ns
from coprs.views.webhooks_ns import webhooks_general


from coprs.exceptions import ObjectNotFound, AccessRestricted, BadRequest, CoprHttpException
from .context_processors import include_banner, inject_fedmenu, counter_processor

setup_log()

app.register_blueprint(api_ns.api_ns)
app.register_blueprint(apiv3_ns.apiv3_ns)
app.register_blueprint(admin_ns.admin_ns)
app.register_blueprint(coprs_ns.coprs_ns)
app.register_blueprint(misc.misc)
app.register_blueprint(backend_ns.backend_ns)
app.register_blueprint(status_ns.status_ns)
app.register_blueprint(recent_ns.recent_ns)
app.register_blueprint(stats_receiver.stats_rcv_ns)
app.register_blueprint(tmp_ns.tmp_ns)
app.register_blueprint(groups_ns)
app.register_blueprint(user_ns)
app.register_blueprint(webhooks_ns)

app.add_url_rule("/", "coprs_ns.coprs_show", coprs_general.coprs_show)


def get_error_handler():
    # http://flask.pocoo.org/docs/1.0/blueprints/#error-handlers
    if flask.request.path.startswith('/api_3/'):
        return apiv3_ns.APIErrorHandler()
    return coprs_ns.UIErrorHandler()


@app.errorhandler(404)
@app.errorhandler(ObjectNotFound)
def handle_404(error):
    error_handler = get_error_handler()
    return error_handler.handle_404(error)


@app.errorhandler(403)
@app.errorhandler(AccessRestricted)
def handle_403(error):
    error_handler = get_error_handler()
    return error_handler.handle_403(error)


@app.errorhandler(400)
@app.errorhandler(BadRequest)
def handle_400(error):
    error_handler = get_error_handler()
    return error_handler.handle_400(error)


@app.errorhandler(500)
@app.errorhandler(CoprHttpException)
def handle_500(error):
    error_handler = get_error_handler()
    return error_handler.handle_500(error)


app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

from coprs.rest_api import rest_api_bp, register_api_error_handler, URL_PREFIX
register_api_error_handler(app)
app.register_blueprint(rest_api_bp, url_prefix=URL_PREFIX)
# register_api(app, db)

from flask_sqlalchemy import models_committed
models_committed.connect(coprs.whoosheers.CoprWhoosheer.on_commit, sender=app)

# Serve static files from system-wide RPM files
@app.route('/system_static/<component>/<path:filename>')
@app.route('/system_static/<path:filename>')
def system_static(filename, component=""):
    """
    :param component: name of the javascript component provided by a RPM package
                      do not confuse with a name of the RPM package itself
                      (e.g. 'jquery' component is provided by 'js-jquery1' package)
    :param filename: path to a file relative to the component root directory
    :return: content of a static file
    """
    path = os.path.join("/usr/share/javascript", component)
    return flask.send_from_directory(path, filename)
