import json
import time
from coprs import db
from coprs import models
from coprs import helpers


class ActionsLogic(object):

    @classmethod
    def get(cls, action_id):
        """
        Return single action identified by `action_id`
        """

        query = models.Action.query.filter(models.Action.id == action_id)
        return query

    @classmethod
    def get_waiting(cls):
        """
        Return actions that aren't finished
        """

        query = (models.Action.query
                 .filter(models.Action.result ==
                         helpers.BackendResultEnum("waiting"))
                 .filter(models.Action.action_type !=
                         helpers.ActionTypeEnum("legal-flag"))
                 .order_by(models.Action.created_on.asc()))

        return query

    @classmethod
    def get_by_ids(cls, ids):
        """
        Return actions matching passed `ids`
        """

        return models.Action.query.filter(models.Action.id.in_(ids))

    @classmethod
    def update_state_from_dict(cls, action, upd_dict):
        """
        Update `action` object with `upd_dict` data

        Updates result, message and ended_on parameters.
        """

        for attr in ["result", "message", "ended_on"]:
            value = upd_dict.get(attr, None)
            if value:
                setattr(action, attr, value)

        db.session.add(action)

    @classmethod
    def send_createrepo(cls, username, coprname, chroots):
        data_dict = {
            "username": username,
            "projectname": coprname,
            "chroots": chroots
        }
        action = models.Action(
            action_type=helpers.ActionTypeEnum("createrepo"),
            object_type="None",
            object_id=0,
            old_value="",
            data=json.dumps(data_dict),
            created_on=int(time.time()),
        )
        db.session.add(action)
