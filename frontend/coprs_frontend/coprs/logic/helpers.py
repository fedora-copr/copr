# coding: utf-8
import time

def slice_query(query, limit=100, offset=0):
    """
    :param Query query:
    :param int limit:
    :param int offset:
    :rtype: Query
    """
    return query.limit(limit).offset(offset)

def get_graph_parameters(type):
    if type is "10min":
        # 24 hours with 10 minute intervals
        step = 600
        steps = 144
    elif type is "30min":
        # 24 hours with 30 minute intervals
        step = 1800
        steps = 48
    elif type is "24h":
        # 90 days with 24 hour intervals
        step = 86400
        steps = 90

    end = int(time.time())
    end = end - (end % step) # align graph interval to a multiple of step
    start = end - (steps * step)

    return {
        "type": type,
        "step": step,
        "steps": steps,
        "start": start,
        "end": end,
    }
