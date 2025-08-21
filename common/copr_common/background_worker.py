"""
Helper methods/classes for 'copr-backend-*' scripts.
"""

import os
import sys
import argparse
import logging
import daemon

import setproctitle

from copr_common.helpers import nullcontext
from copr_common.redis_helpers import get_redis_connection


class BackgroundWorker:
    """
    copr-backend-process-* abstraction
    """

    redis_logger_id = 'unknown'
    frontend_client = None
    _redis_conn = None

    def __init__(self):
        # just setup temporary stderr logger
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(logging.StreamHandler())

        if os.getuid() == 0:
            self.log.error("running as UID=0 (root), probably not expected")
            sys.exit(1)

        self.opts = None
        self.args = self._get_argparser().parse_args(sys.argv[1:])

    @staticmethod
    def setproctitle(text):
        """ set the process title, beginning with the script name """
        command = " ".join(sys.argv)
        setproctitle.setproctitle("{} (command: {})".format(text, command))

    @property
    def _redis(self):
        if not self._redis_conn:
            self._redis_conn = get_redis_connection(self.opts)
        return self._redis_conn

    def redis_set_worker_flag(self, flag, value=1):
        """
        Set flag in Reids DB for corresponding worker.  NO-OP if there's no
        redis connection (when run manually).
        """
        if not self.has_wm:
            return
        self._redis.hset(self.args.worker_id, flag, value)

    def redis_get_worker_flag(self, flag):
        """
        Get flag from Redis DB entry of corresponding worker.  If there's no
        Redis connection (manual run) return None
        """
        if not self.has_wm:
            return None
        return self._redis.hget(self.args.worker_id, flag)

    @classmethod
    def _get_argparser(cls):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--worker-id",
            help=("worker ID which already exists in redis DB (used by "
                  "WorkerManager only, copr-internal option)"),
        )
        parser.add_argument(
            "--daemon",
            action='store_true',
            help="execute the task on background, as daemon process"
        )
        parser.add_argument(
            "--silent",
            action='store_true',
            help="don't print logs, even when run without --daemon",
        )
        parser.add_argument(
            "--backend-config",
            help="alternative path to /etc/copr/copr-be.conf",
        )
        cls.adjust_arg_parser(parser)
        return parser

    @classmethod
    def adjust_arg_parser(cls, parser):
        """
        The inherited worker class will need more commandline options than those
        we provide by default.  Override is required.
        """
        raise NotImplementedError()

    def handle_task(self):
        """
        Abstract method for handling the task.  This should never throw any
        exception, and we don't expect it to return any value.
        """
        raise NotImplementedError()

    @property
    def has_wm(self):
        """
        Returns True if worker manager started this process, and False
        if it is manual run.
        """
        return bool(self.worker_id)

    @property
    def worker_id(self):
        """ Return worker ID if set by worker manager, or None.  """
        return self.args.worker_id

    def _wm_started(self):
        if not self.has_wm:
            return True

        self.redis_set_worker_flag('started', 1)
        self.redis_set_worker_flag('PID', os.getpid())

        data = self._redis.hgetall(self.args.worker_id)
        if 'allocated' not in data:
            self.log.error("too slow box, manager thinks we are dead")
            self._redis.delete(self.args.worker_id)
            return False

        # There's still small race on a very slow box (TOCTOU in manager, the
        # db entry can be deleted after our check above ^^).  But we don't risk
        # anything else than concurrent run of multiple workers in such case.
        return True

    def preparations_for_manager(self):
        """
        Hook called right after creating the worker process (daemonized,
        if requested) and after successful notification to Manager that
        worker started.  For manual runs (no --worker-id specified) this
        hook isn't called at all.
        """

    def _daemonized_part(self):
        # notify WorkerManager first, to minimize race window
        self._wm_started()
        if self.has_wm:
            self.preparations_for_manager()
        try:
            self.handle_task()
        except Exception as exc:  # pylint: disable=W0703
            self.log.exception("unexpected failure %s", str(exc))
            sys.exit(1)

    def process(self):
        """ process the task """
        context = nullcontext()
        if self.args.daemon:
            context = daemon.DaemonContext(umask=0o022)

        with context:
            self._daemonized_part()
