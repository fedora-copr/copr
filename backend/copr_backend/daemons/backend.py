# coding: utf-8

import grp
import pwd
import sys

import lockfile
from daemon import DaemonContext
from copr_backend.frontend import FrontendClient

from ..exceptions import CoprBackendError, FrontendClientException
from ..helpers import BackendConfigReader, get_redis_logger


class CoprBackend(object):
    """
    COPR backend head process.

    :param config_file: path to the backend configuration file
    :param ext_opts: additional options for backend
    """

    def __init__(self, config_file=None, ext_opts=None):
        if not config_file:
            raise CoprBackendError("Must specify config_file")

        self.config_file = config_file
        self.ext_opts = ext_opts  # to show our cli options for read_conf()

        self.config_reader = BackendConfigReader(self.config_file, self.ext_opts)
        self.opts = None
        self.update_conf()

        self.log = get_redis_logger(self.opts, "backend.main", "backend")
        self.frontend_client = FrontendClient(self.opts, self.log)

    def update_conf(self):
        """
        Update backend config from config file
        """
        self.opts = self.config_reader.read()

    def run(self):
        """
        Starts backend process. Control sub process start/stop.
        """
        self.update_conf()
        self.log.info("Initial config: %s", self.opts)

        try:
            self.log.info("Rescheduling old unfinished builds")
            self.frontend_client.reschedule_all_running()
        except FrontendClientException as err:
            self.log.exception(err)
            raise CoprBackendError(err)


def run_backend(opts):
    """
    Start main backend daemon

    :param opts: Munch object with command line options

    Expected **opts** fields:
        - `config_file` - path to the backend config file
        - `daemonize` - boolean flag to enable daemon mode
        - `pidfile` - path to the backend pidfile

        - `daemon_user`
        - `daemon_group`
    """
    cbe = None
    try:
        context = DaemonContext(
            pidfile=lockfile.FileLock(opts.pidfile),
            # gid=grp.getgrnam("copr").gr_gid,
            # uid=pwd.getpwnam("copr").pw_uid,
            gid=grp.getgrnam(opts.daemon_user).gr_gid,
            uid=pwd.getpwnam(opts.daemon_group).pw_uid,
            detach_process=opts.daemonize,
            umask=0o22,
            stderr=sys.stderr
        )
        with context:
            cbe = CoprBackend(opts.config_file, ext_opts=opts)
            cbe.run()
    except (Exception, KeyboardInterrupt):
        sys.stderr.write("Killing/Dying\n")
        raise
