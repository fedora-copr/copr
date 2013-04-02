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
    legal_flags = models.Action.query.filter(models.Action.action_type==helpers.ActionTypeEnum('legal-flag')).\
                                      filter(models.Action.object_type=='copr').\
                                      filter(models.Action.ended_on==None).\
                                      order_by(models.Action.created_on.desc()).\
                                      all()

    ids = map(lambda x: x.object_id, legal_flags)
    # if there are no ids, we would trigger "IN" query with empty set, which
    # is not very good (and sqlalchemy complains about it)
    coprs = coprs_logic.CoprsLogic.get_multiple(flask.g.user, ids=ids).all() if ids else []
    for flag in legal_flags:
        # handle the situation where copr was deleted in the meanwhile
        copr = filter(lambda x: flag.object_id == x.id, coprs)
        flag.copr = copr[0] if copr else None

    return flask.render_template('admin/legal-flag.html',
                                 legal_flags=legal_flags)

@admin_ns.route('/legal-flag/<int:action_id>/resolve/', methods=['POST'])
@login_required(role=helpers.RoleEnum('admin'))
def legal_flag_resolve(action_id):
    action = models.Action.query.filter(models.Action.id==action_id).\
                                 update({'ended_on': int(time.time())})
    db.session.commit()
    flask.flash('Legal flag resolved')
    return flask.redirect(flask.url_for('admin_ns.legal_flag'))
