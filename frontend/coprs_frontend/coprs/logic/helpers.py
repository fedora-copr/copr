# coding: utf-8

from sqlalchemy.orm.query import Query


def slice_query(query, limit=100, offset=0):
    """
    :param Query query:
    :param int limit:
    :param int offset:
    :rtype: Query
    """
    return query.limit(limit).offset(offset)
