import flask

from coprs import helpers

from coprs.views.admin_ns import admin_ns
from coprs.views.misc import login_required

@admin_ns.route('/')
@login_required(role=helpers.RoleEnum('admin'))
def admin_index():
    return flask.render_template('admin/index.html')
