"""
Web-UI routes related to build batches
"""

from flask import render_template
from coprs.logic.batches_logic import BatchesLogic
from coprs.views.batches_ns import batches_ns


@batches_ns.route("/detail/<int:batch_id>/")
def coprs_batch_detail(batch_id):
    """ Print the list (tree) of batches """
    chain = BatchesLogic.batch_chain(batch_id)
    batch = chain[0]
    deps = chain[1:]
    return render_template("batches/detail.html", batch=batch, deps=deps)
