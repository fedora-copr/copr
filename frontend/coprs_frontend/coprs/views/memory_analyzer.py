"""
Convenience routes to analyze memory usage between requests, used for debugging
purposes only.  To start using this module:

  FLASK_ENV=development MEMORY_ANALYZER=true ./manage.py runserver -p 55555 -h 0.0.0.0 --reload --without-threads

Note the MEMORY_ANALYZER environment variable (needed to enable this module),
and the --without-threads option (needed to avoid tracking each request via a
separate thread).

Experimenting with the memory analyzer goes like this:

    $ curl localhost:55555/ma/diff.txt
    $ copr list-packages @python/python3.10 --with-latest-succeeded-build
    ....
    $ curl localhost:55555/ma/diff-5.txt
    Memory diff: 1.35168 MB
    /usr/lib/python3.9/site-packages/werkzeug/urls.py:399: size=36.0 KiB (+36.0 KiB), count=2 (+2), average=18.0 KiB
    /usr/lib/python3.9/site-packages/werkzeug/urls.py:391: size=2480 B (+2480 B), count=3 (+3), average=827 B
    /usr/lib/python3.9/site-packages/redis/connection.py:725: size=1032 B (+1032 B), count=2 (+2), average=516 B
    /usr/lib/python3.9/site-packages/werkzeug/urls.py:710: size=968 B (+968 B), count=2 (+2), average=484 B
    /usr/lib/python3.9/site-packages/werkzeug/urls.py:167: size=896 B (+896 B), count=2 (+2), average=448 B
"""

import gc
import os
import tracemalloc
import flask
import psutil

# Useful stuff...
#import ipdb
#import objgraph
#import resource
#print 'Memory usage: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

memory_analyzer = flask.Blueprint("memory", __name__, url_prefix="/ma/")

_glob_state = None
process = psutil.Process(os.getpid())

tracemalloc.start()

@memory_analyzer.route("/diff.txt", methods=["GET"])
@memory_analyzer.route("/diff-<int:count>.txt", methods=["GET"])
def diff_in_memory(count=None):
    """ Take a memory snapshot. """

    # cleanup leftovers first
    gc.collect()

    # put a brakpoint here, e.g., and experiment with objgraph
    #ipdb.set_trace()
    #objgraph.most_common_types()
    # ....

    # pylint: disable=global-statement
    global _glob_state
    if _glob_state is None:
        _glob_state = {
            "snapshot": tracemalloc.take_snapshot(),
            "memory": process.memory_info().rss,
        }
        return "first snapshot taken ... memory {}\n".format(_glob_state["memory"])


    new_glob_state = tracemalloc.take_snapshot()
    new_memory = process.memory_info().rss
    stats = new_glob_state.compare_to(_glob_state["snapshot"], "lineno")

    diff_memory = (new_memory - _glob_state["memory"])/1000/1000
    diff_memory = "Memory diff: {} MB".format(diff_memory)

    _glob_state = {
        "snapshot": new_glob_state,
        "memory": new_memory
    }

    messages = [
        diff_memory,
    ]

    if count is not None:
        stats = stats[:count]

    return flask.Response(
        "\n".join(messages + [str(s) for s in stats]) + "\n",
        mimetype="text/plain",
    )
