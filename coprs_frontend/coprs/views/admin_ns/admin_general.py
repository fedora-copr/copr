import time

import flask

from coprs import db
from coprs import helpers
from coprs import models

from coprs.logic import coprs_logic

from coprs.views.admin_ns import admin_ns
from coprs.views.misc import login_required

@admin_ns.route('/')
@login_required(role=helpers.RoleEnum('admin'))
def admin_index():
    return flask.render_template('admin/index.html')

@admin_ns.route('/legal-flag/')
@login_required(role=helpers.RoleEnum('admin'))
def legal_flag():
    legal_flags = models.LegalFlag.query.outerjoin(models.LegalFlag.copr).\
                                         options(db.contains_eager(models.LegalFlag.copr)).\
                                         filter(models.LegalFlag.resolved_on==None).\
                                         order_by(models.LegalFlag.raised_on.desc()).\
                                         all()

    return flask.render_template('admin/legal-flag.html',
                                 legal_flags=legal_flags)

@admin_ns.route('/legal-flag/<int:flag_id>/resolve/', methods=['POST'])
@login_required(role=helpers.RoleEnum('admin'))
def legal_flag_resolve(flag_id):
    legal_flag = models.LegalFlag.query.filter(models.LegalFlag.id==flag_id).\
                                        update({'resolved_on': int(time.time()),
                                                'resolver_id': flask.g.user.id})
    db.session.commit()
    flask.flash('Legal flag resolved')
    return flask.redirect(flask.url_for('admin_ns.legal_flag'))
