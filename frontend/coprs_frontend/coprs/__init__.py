# This is very complicated module.  TODO: drop the ignores
# pylint: disable=wrong-import-order,wrong-import-position,cyclic-import

import os
import flask

from werkzeug.routing import RequestRedirect
from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager
try:
    from flask_caching import Cache
except ImportError:
    from flask_cache import Cache
from flask_openid import OpenID
from flask_whooshee import Whooshee
from openid_teams.teams import TeamsResponse

from coprs.redis_session import RedisSessionInterface
from coprs.request import get_request_class

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

profiler_enabled = bool(app.config.get('PROFILER', False))
try:
    # needs to be installed using pip3
    import flask_profiler
except ImportError:
    # This is intended to not be presented. Even on most devel setups.
    profiler_enabled = False

def setup_profiler(flask_app, enabled):
    """ This creates /flask-profiler/ route """
    flask_app.config["flask_profiler"] = {
        "enabled": enabled,
        "storage": {
            "engine": "sqlite",
            "FILE": "/tmp/profiler.sqlite",
        },
        "basicAuth":{
            "enabled": True,
            "username": "admin",
            "password": "admin"
        },
        "ignore": [
               "^/static/.*"
           ]
    }
    if enabled:
        flask_profiler.init_app(flask_app)

import coprs.filters
import coprs.log
from coprs.log import setup_log
import coprs.whoosheers

from coprs.helpers import RedisConnectionProvider
rcp = RedisConnectionProvider(config=app.config)
app.session_interface = RedisSessionInterface(rcp.get_connection())

cache_rcp = RedisConnectionProvider(config=app.config, db=1)
cache = Cache(app, config={
    'CACHE_REDIS_HOST': cache_rcp.host,
    'CACHE_REDIS_PORT': cache_rcp.port,
})
app.cache = cache

app.request_class = get_request_class(app)

from coprs.views import admin_ns
from coprs.views.admin_ns import admin_general
from coprs.views import api_ns
from coprs.views.api_ns import api_general
from coprs.views import apiv3_ns
from coprs.views.apiv3_ns import (
    apiv3_general, apiv3_builds, apiv3_packages, apiv3_projects,
    apiv3_project_chroots, apiv3_modules, apiv3_build_chroots,
    apiv3_mock_chroots, apiv3_permissions, apiv3_webhooks, apiv3_monitor,
)

from coprs.views import batches_ns
from coprs.views.batches_ns import coprs_batches
from coprs.views import coprs_ns
from coprs.views.coprs_ns import coprs_builds
from coprs.views.coprs_ns import coprs_general
from coprs.views.coprs_ns import coprs_chroots
from coprs.views.coprs_ns import coprs_packages
from coprs.views.coprs_ns import pagination_redirect
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
from coprs.views.rss_ns import rss_ns
from coprs.views.rss_ns import rss_general
from coprs.exceptions import (
    AccessRestricted,
    BadRequest,
    CoprHttpException,
    ConflictingRequest,
    MalformedArgumentException,
    ObjectNotFound,
    NonAdminCannotCreatePersistentProject,
    NonAdminCannotDisableAutoPrunning,
)
from coprs.views.explore_ns import explore_ns
from coprs.error_handlers import get_error_handler
import coprs.context_processors

with app.app_context():
    setup_log()

app.register_blueprint(api_ns.api_ns)
app.register_blueprint(apiv3_ns.apiv3_ns)
app.register_blueprint(admin_ns.admin_ns)
app.register_blueprint(batches_ns.batches_ns)
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
app.register_blueprint(rss_ns)
app.register_blueprint(explore_ns)

if app.config["MEMORY_ANALYZER"]:
    from coprs.views.memory_analyzer import memory_analyzer
    app.register_blueprint(memory_analyzer)

app.add_url_rule("/", "coprs_ns.coprs_show", coprs_general.coprs_show)


@app.errorhandler(RequestRedirect)
def handle_request_redirect(error):
    return error.get_response(None)


@app.errorhandler(Exception)
def handle_exceptions(error):
    error_handler = get_error_handler()
    return error_handler.handle_error(error)


app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

setup_profiler(app, profiler_enabled)

from flask_sqlalchemy import models_committed
models_committed.connect(coprs.whoosheers.CoprWhoosheer.on_commit, sender=app)

# Serve static files from system-wide RPM files
@app.route('/system_static/<component>/<path:filename>')
@app.route('/system_static/<path:filename>')
def system_static(filename, component=""):
    """
    :param component: name of the javascript component provided by a RPM package
                      do not confuse with a name of the RPM package itself
                      (e.g. 'jquery' component is provided by 'js-jquery' package)
    :param filename: path to a file relative to the component root directory
    :return: content of a static file
    """
    path = os.path.join("/usr/share/javascript", component)
    return flask.send_from_directory(path, filename)
