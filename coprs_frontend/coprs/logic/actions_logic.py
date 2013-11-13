from coprs import db
from coprs import models
from coprs import helpers


class ActionsLogic(object):
    @classmethod
    def get(cls, action_id):
        """ Return single action identified by `action_id` """
        query = models.Action.query.filter(models.Action.id == action_id)
        return query

    @classmethod
    def get_waiting(cls):
        """ Return actions that aren't finished """
        query = (models.Action.query
                 .filter(models.Action.result ==
                         helpers.BackendResultEnum('waiting'))
                 .order_by(models.Action.created_on.asc()))

        return query

    @classmethod
    def get_by_ids(cls, ids):
        """ Return actions matching passed `ids` """
        return models.Action.query.filter(models.Action.id.in_(ids))

    @classmethod
    def update_state_from_dict(cls, action, upd_dict):
        """
        Update `action` object with `upd_dict` data

        Updates result, message and ended_on parameters.
        """
        for attr in ['result', 'message', 'ended_on']:
            value = upd_dict.get(attr, None)
            if value:
                setattr(action, attr, value)

        db.session.add(action)
