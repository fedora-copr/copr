"""
Helper methods/classes for 'copr-backend-*' scripts.
"""

import os
import sys
import argparse
import contextlib
import logging
import daemon

from copr_backend.frontend import FrontendClient
from copr_backend.helpers import (BackendConfigReader, get_redis_logger,
                                  get_redis_connection)


class BackgroundWorker:
    redis_logger_id = 'unknown'
    frontend_client = None
    _redis_conn = None

    def __init__(self):
        # just setup temporary stderr logger
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(logging.StreamHandler())

        if os.getuid() == 0:
            self.log.error("this needs to be run as 'copr' user")
            sys.exit(1)

        self.args = self._get_argparser().parse_args()
        be_cfg = self.args.backend_config or '/etc/copr/copr-be.conf'
        self.opts = BackendConfigReader(be_cfg).read()

    @property
    def _redis(self):
        if not self._redis_conn:
            self._redis_conn = get_redis_connection(self.opts)
        return self._redis_conn

    def redis_hset(self, key, val):
        if not self.has_wm:
            return
        self._redis.hset(self.args.worker_id, key, val)

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
            "--backend-config",
            help="alternative path to /etc/copr/copr-be.conf",
        )
        cls.adjust_arg_parser(parser)
        return parser

    @classmethod
    def adjust_arg_parser(cls, parser):
        pass

    def handle_task(self):
        """
        Abstract method for handling the task.  This should never hrow any
        exception, and no return value is expected.
        """
        raise NotImplementedError()

    @property
    def has_wm(self):
        """
        Returns True if worker manager started this process, and False
        if it is manual run.
        """
        return self.args.worker_id

    def _wm_started(self):
        if not self.has_wm:
            return True

        self.redis_hset('started', 1)
        self.redis_hset('PID', os.getpid())

        data = self._redis.hgetall(self.args.worker_id)
        if 'allocated' not in data:
            self.log.error("too slow box, manager thinks we are dead")
            self._redis.delete(self.args.worker_id)
            return False

        # There's still small race on a very slow box (TOCTOU in manager, the
        # db entry can be deleted after our check above ^^).  But we don't risk
        # anything else than concurrent run of multiple workers in such case.
        return True

    def _switch_logger_to_redis(self):
        if not self.has_wm:
            return

        logger_name = '{}.{}.pid-{}'.format(
            sys.argv[0],
            'managed' if self.args.worker_id else 'manual',
            os.getpid(),
        )

        self.log = get_redis_logger(self.opts, logger_name,
                                    self.redis_logger_id)
        if not self.args.daemon:
            # when executing from commandline - on foreground - we want to
            # print something to stderr as well
            self.log.addHandler(logging.StreamHandler())

    def _daemonized_part(self):
        # notify WorkerManager first, to minimize race window
        self._wm_started()

        # setup logging early, to have as complete logs as possible
        self._switch_logger_to_redis()

        self.frontend_client = FrontendClient(self.opts, self.log)

        try:
            self.handle_task()
        except Exception as exc:  # pylint: disable=W0703
            self.log.exception("unexpected failure %s", str(exc))
            sys.exit(1)

    def process(self):
        """ process the task """
        context = contextlib.nullcontext()
        if self.args.daemon:
            context = daemon.DaemonContext(umask=0o022)

        with context:
            self._daemonized_part()
