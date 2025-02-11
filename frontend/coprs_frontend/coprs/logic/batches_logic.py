"""
Methods for working with build Batches.
"""

import contextlib
import anytree
import backoff

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text
from coprs import app, db, cache
from coprs.helpers import WorkList
from coprs.models import Batch, Build
from coprs.exceptions import BadRequest
import coprs.logic.builds_logic as bl


log = app.logger


@backoff.on_exception(backoff.expo, SQLAlchemyError, max_time=20, logger=log)
def _lock_table(table):
    # It seems that every database has different locking commands and we
    # don't care about anything else than PostgreSQL.
    if db.engine.name != "postgresql":
        return

    # EXCLUSIVE mode locks the whole table for write operations
    # (while reading is not blocked) until the end of the transaction
    # (commit / rollback)
    with db.engine.connect() as connection:
        connection.execute(text("LOCK TABLE {} IN EXCLUSIVE MODE;".format(
            # https://docs.sqlalchemy.org/en/13/core/internals.html#sqlalchemy.sql.compiler.IdentifierPreparer.quote
            db.engine.dialect.identifier_preparer.quote(table)
        )))


@contextlib.contextmanager
def locked_table(table_name, reason="not specified"):
    """
    Create a sub-transaction with locked table (PG only).  Use with with.
    """
    with db.session.begin_nested():
        log.debug("Locking table %s (%s)", table_name, reason)
        _lock_table(table_name)
        log.debug("Lock acquired (%s)", reason)
        yield
    log.debug("Lock released (%s)", reason)


class BatchesLogic:
    """ Batch logic entrypoint """

    @classmethod
    def get_batch_or_create(cls, build_id, requestor, modify=False):
        """
        Put the build into a new batch, and return the batch.  If the build is
        already assigned to any batch, do nothing and return the batch.

        Locks the build for updates, may block!
        """

        # We don't want to create a new batch if one already exists, but there's
        # the concurrency problem so we need to lock the build instance for
        # writing.
        build = db.session.get(Build, build_id)
        if not build:
            raise BadRequest("Build {} doesn't exist".format(build_id))

        error = build.batching_user_error(requestor, modify)
        if error:
            raise BadRequest(error)

        # Somewhat pedantically, we _should_ lock the batch (if exists)
        # here because the query for 'build.finished' and
        # 'build.batch.finished' is a bit racy (backend workers may
        # asynchronously make the build/batch finished, and we may still
        # assign some new build to a just finished batch).
        # Or #2107 can happen.
        with locked_table("batch", "for_build_id={}".format(build_id)):
            if not build.batch:
                build.batch = Batch()
                db.session.add(build.batch)

        return build.batch

    @staticmethod
    def pending_batches():
        """
        Query for all still not-finished batches, order by id ASC
        """
        batches = set()
        query = bl.BuildsLogic.processing_builds().filter(Build.batch_id.isnot(None))
        for build in query.all():
            if build.batch:
                batches.add(build.batch)
        return batches

    @classmethod
    @cache.memoize(timeout=60)
    def pending_batch_count_cached(cls):
        """
        Return the number of currently processed Batch instances (where at least
        one build is not yet fully finished).  This is a pretty expensive number
        and yet we show it on every /stats/ page (and on many others) — that's
        why we cache it.
        """
        return len(cls.pending_batches())

    @classmethod
    def pending_batch_trees(cls):
        """
        Get all the currently processing batches, together with all the
        dependency batches which are already finished -- and keep them ordered
        in list based on theirs ID and dependencies.
        """
        roots = []
        node_map = {}
        def get_mapped_node(batch):
            if batch.id in node_map:
                return node_map[batch.id]
            node_map[batch.id] = anytree.Node(batch)
            return node_map[batch.id]

        # go through all the batches transitively
        pending_batches = cls.pending_batches()
        wl = WorkList(pending_batches)
        while not wl.empty:
            batch = wl.pop()
            node = get_mapped_node(batch)
            if batch.blocked_by_id:
                parent_node = get_mapped_node(batch.blocked_by)
                node.parent = parent_node
                wl.schedule(batch.blocked_by)
            else:
                roots.append(node)
        return roots

    @classmethod
    def batch_chain(cls, batch_id):
        """
        Return the batch_with batch_id, and all the transitively blocking
        batches in one list.
        """
        chain = []
        batch = Batch.query.get(batch_id)
        while batch:
            chain.append(batch)
            batch = batch.blocked_by
        return chain

    # STILL PENDING
    # =============
    # => some builds are: waiting, pending, starting, running, importing
    # => the rest is: succeeded/failed
    #
    # SUCCEEDED
    # =========
    # => all builds succeeded
    #
    # FAILED, BUT FIXABLE
    # ===================
    # => all builds are succeeded or failed
    # => timeout is OK: last ended_on is >= time.time() - deadline
    #
    # FAILED
    # ======
    # => some builds failed
    # => timeout is out
