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
                                                                       '__columns_only__': ['id', 'name'],
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
    actions = models.Action.query.filter(models.Action.result==helpers.BackendResultEnum('waiting')).all()

    return flask.jsonify({'actions': [action.to_dict(options={'__columns_except__': ['result', 'message', 'ended_on']}) for action in actions]})


# TODO: this is very similar to update_builds, we should pull out the common functionality into a single function
@backend_ns.route('/update_actions/', methods=['POST', 'PUT'])
@misc.backend_authenticated
def update_actions():
    to_update = {}
    for action in flask.request.json['actions']:
        to_update[action['id']] = action

    if not to_update:
        return json.dumps({'warning': 'No parsed actions'})

    existing = {}
    for action in models.Action.query.filter(models.Action.id.in_(to_update.keys())).all():
        existing[action.id] = action

    non_existing_ids = list(set(to_update.keys()) - set(existing.keys()))

    for i, action in existing.items():
        existing[i].result = to_update[i]['result']
        existing[i].message = to_update[i]['message']
        existing[i].ended_on = to_update[i]['ended_on']

    db.session.commit()

    return flask.jsonify({'updated_actions_ids': list(existing.keys()), 'non_existing_actions_ids': non_existing_ids})
