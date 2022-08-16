# coding: utf-8
import time


def get_graph_parameters(type):
    if type == "10min":
        # 24 hours with 10 minute intervals
        step = 600
        steps = 144
    elif type == "30min":
        # 24 hours with 30 minute intervals
        step = 1800
        steps = 48
    elif type == "24h":
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
