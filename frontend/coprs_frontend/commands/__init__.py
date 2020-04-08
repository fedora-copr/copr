import functools
import sqlalchemy
from coprs import models


def deprioritize_actions(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        sqlalchemy.event.listen(models.Action, "before_insert", _deprioritize_action)
        return f(*args, **kwargs)
    return wrapper


def _deprioritize_action(mapper, connection, target):
    target.priority = 99
