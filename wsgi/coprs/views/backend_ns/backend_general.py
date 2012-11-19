import flask

from coprs import db
from coprs import models

from coprs.logic import builds_logic

from coprs.views.backend_ns import backend_ns

@backend_ns.route('/waiting_builds/')
def waiting_builds():
    query = builds_logic.BuildsLogic.get_waiting_builds(None)

    builds = query[0:10]
    return flask.jsonify({'builds': [build.to_dict(options = {'copr': {'owner': {'__columns_except__': ['openid_name', 'proven'] },
                                                                       '__columns_except__': ['chroots', 'repos'],
                                                                       '__included_ids__': False},
                                                              '__included_ids__': False}) for build in builds]})
