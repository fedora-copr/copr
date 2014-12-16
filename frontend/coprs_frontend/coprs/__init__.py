from __future__ import with_statement

import os
import flask

from flask_sqlalchemy import SQLAlchemy
from flask_openid import OpenID
from flask_whooshee import Whooshee

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


oid = OpenID(app, app.config["OPENID_STORE"], safe_roots=[])
db = SQLAlchemy(app)
whooshee = Whooshee(app)


import coprs.filters
import coprs.log
from coprs.log import setup_log
import coprs.models
import coprs.whoosheers

from coprs.helpers import RedisConnectionProvider
rcp = RedisConnectionProvider(config=app.config)

from coprs.views import admin_ns
from coprs.views.admin_ns import admin_general
from coprs.views import api_ns
from coprs.views.api_ns import api_general
from coprs.views import coprs_ns
from coprs.views.coprs_ns import coprs_builds
from coprs.views.coprs_ns import coprs_general
from coprs.views.coprs_ns import coprs_chroots
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


from .context_processors import include_banner, inject_fedmenu

setup_log()

app.register_blueprint(api_ns.api_ns)
app.register_blueprint(admin_ns.admin_ns)
app.register_blueprint(coprs_ns.coprs_ns)
app.register_blueprint(misc.misc)
app.register_blueprint(backend_ns.backend_ns)
app.register_blueprint(status_ns.status_ns)
app.register_blueprint(recent_ns.recent_ns)
app.register_blueprint(stats_receiver.stats_rcv_ns)
app.register_blueprint(tmp_ns.tmp_ns)

app.add_url_rule("/", "coprs_ns.coprs_show", coprs_general.coprs_show)

from rest_api import rest_api_bp, register_api_error_handler, URL_PREFIX
register_api_error_handler(app)
app.register_blueprint(rest_api_bp, url_prefix=URL_PREFIX)
# register_api(app, db)
