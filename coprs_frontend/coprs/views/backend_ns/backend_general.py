import flask

from coprs import db
from coprs import helpers
from coprs import models

from coprs.logic import builds_logic

from coprs.views import misc
from coprs.views.backend_ns import backend_ns

@backend_ns.route('/waiting_builds/')
def waiting_builds():
    query = builds_logic.BuildsLogic.get_waiting_builds(None)

    builds = query[0:10]
    return flask.jsonify({'builds': [build.to_dict(options = {'copr': {'owner': {},
                                                                       '__columns_except__': ['chroots', 'repos', 'build_count'],
                                                                       '__included_ids__': False},
                                                              '__included_ids__': False}) for build in builds]})

@backend_ns.route('/update_builds/', methods = ['POST', 'PUT'])
@misc.backend_authenticated
def update_builds():
    to_update = {}
    for build in flask.request.json['builds']: # first get ids of sent builds
        to_update[build['id']] = build

    if not to_update:
        return json.dumps({'warning': 'No parsed builds'})

    existing = {} # create a dict of existing builds {build.id: build, ...}
    for build in builds_logic.BuildsLogic.get_by_ids(None, to_update.keys()).all():
        existing[build.id] = build

    non_existing_ids = list(set(to_update.keys()) - set(existing.keys()))

    for i, build in existing.items(): # actually update existing builds
        builds_logic.BuildsLogic.update_state_from_dict(None, build, to_update[i])

    db.session.commit()

    return flask.jsonify({'updated_builds_ids': list(existing.keys()), 'non_existing_builds_ids': non_existing_ids})

@backend_ns.route('/waiting_actions/')
def waiting_actions():
    actions = models.Action.query.filter(models.Action.backend_result==helpers.BackendResultEnum('waiting')).all()

    return flask.jsonify({'actions': [action.to_dict(options={'__columns_except__': ['backend_result', 'backend_message']}) for action in actions]})
