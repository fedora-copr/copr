from sqlalchemy import desc
from coprs import models


class DistGitLogic:
    @classmethod
    def ordered(cls):
        'get the default dist git instance object'
        query = models.DistGitInstance.query
        return query.order_by(desc('priority'), 'name')

    @classmethod
    def get_with_default(cls, distgit_name=None):
        if distgit_name is None:
            return cls.ordered().limit(1).one()
        query = models.DistGitInstance.query.filter_by(name=distgit_name)
        return query.one()
