from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import fcntl
from operator import methodcaller
import optparse
import ConfigParser
import os
import sys
import datetime
import traceback

from bunch import Bunch
from redis import StrictRedis

from copr.client import CoprClient
from backend.constants import DEF_BUILD_USER, DEF_BUILD_TIMEOUT, DEF_CONSECUTIVE_FAILURE_THRESHOLD, \
    CONSECUTIVE_FAILURE_REDIS_KEY
from backend.exceptions import CoprBackendError

try:
    import fedmsg
except ImportError:
    # fedmsg is optional
    fedmsg = None


class SortedOptParser(optparse.OptionParser):
    """Optparser which sorts the options by opt before outputting --help"""

    def format_help(self, formatter=None):
        self.option_list.sort(key=methodcaller("get_opt_string"))
        return optparse.OptionParser.format_help(self)


def _get_conf(cp, section, option, default, mode=None):
    """
    To make returning items from config parser less irritating

    :param mode: convert obtained value, possible modes:
      - None (default): do nothing
      - "bool" or "boolean"
      - "int"
      - "float"
    """

    if cp.has_section(section) and cp.has_option(section, option):
        if mode is None:
            return cp.get(section, option)
        elif mode in ["bool", "boolean"]:
            return cp.getboolean(section, option)
        elif mode == "int":
            return cp.getint(section, option)
        elif mode == "float":
            return cp.getfloat(section, option)
        elif mode == "path":
            path = cp.get(section, option)
            if path.startswith("~"):
                path = os.path.expanduser(path)
            path = os.path.abspath(path)
            path = os.path.normpath(path)

            return path
    return default


class BackendConfigReader(object):
    def __init__(self, config_file=None, ext_opts=None):
        self.config_file = config_file or "/etc/copr/copr-be.conf"
        self.ext_opts = ext_opts

    def read(self):
        try:
            opts = self._read_unsafe()
            if self.ext_opts:
                for key, value in self.ext_opts.items():
                    setattr(opts, key, value)

            if not opts.destdir:
                raise CoprBackendError(
                    "Incomplete Config - must specify"
                    " destdir in configuration")

            return opts

        except ConfigParser.Error as e:
            raise CoprBackendError(
                "Error parsing config file: {0}: {1}".format(
                    self.config_file, e))

    def _read_unsafe(self):
        cp = ConfigParser.ConfigParser()
        cp.read(self.config_file)

        opts = Bunch()
        opts.results_baseurl = _get_conf(
            cp, "backend", "results_baseurl", "http://copr")

        # TODO: this should be built from frontend_base_url + '/backend'
        opts.frontend_url = _get_conf(
            cp, "backend", "frontend_url", "http://coprs/rest/api")

        # We need this to access public api
        opts.frontend_base_url = _get_conf(
            cp, "backend", "frontend_base_url", "http://coprs/")

        opts.frontend_auth = _get_conf(
            cp, "backend", "frontend_auth", "PASSWORDHERE")

        opts.do_sign = _get_conf(
            cp, "backend", "do_sign", False, mode="bool")

        opts.keygen_host = _get_conf(
            cp, "backend", "keygen_host", "copr-keygen.cloud.fedoraproject.org")

        opts.build_user = _get_conf(
            cp, "backend", "build_user", DEF_BUILD_USER)

        opts.build_groups_count = _get_conf(
            cp, "backend", "build_groups", 1, mode="int")

        opts.build_groups = []
        for group_id in range(opts.build_groups_count):
            archs = _get_conf(cp, "backend",
                              "group{0}_archs".format(group_id),
                              default="i386,x86_64").split(",")
            group = {
                "id": int(group_id),
                "name": _get_conf(cp, "backend", "group{0}_name".format(group_id), "PC"),
                "archs": archs,
                "spawn_playbook": _get_conf(
                    cp, "backend", "group{0}_spawn_playbook".format(group_id),
                    default="/srv/copr-work/provision/builderpb-PC.yml"),
                "terminate_playbook": _get_conf(
                    cp, "backend", "group{0}_terminate_playbook".format(group_id),
                    default="/srv/copr-work/provision/terminatepb-PC.yml"),
                "max_workers": _get_conf(
                    cp, "backend", "group{0}_max_workers".format(group_id),
                    default=32, mode="int"),
                "max_vm_total": _get_conf(
                    cp, "backend", "group{}_max_vm_total".format(group_id),
                    # default=16, mode="int"),
                    default=2, mode="int"),
                "max_vm_per_user": _get_conf(
                    cp, "backend", "group{}_max_vm_total".format(group_id),
                    default=2, mode="int"),
                "max_spawn_processes": _get_conf(
                    cp, "backend", "group{}_max_spawn_processes".format(group_id),
                    default=2, mode="int"),

            }
            opts.build_groups.append(group)

        opts.destdir = _get_conf(cp, "backend", "destdir", None, mode="path")

        opts.exit_on_worker = _get_conf(
            cp, "backend", "exit_on_worker", False, mode="bool")
        opts.fedmsg_enabled = _get_conf(
            cp, "backend", "fedmsg_enabled", False, mode="bool")
        opts.sleeptime = _get_conf(
            cp, "backend", "sleeptime", 10, mode="int")
        opts.timeout = _get_conf(
            cp, "builder", "timeout", DEF_BUILD_TIMEOUT, mode="int")
        opts.consecutive_failure_threshold = _get_conf(
            cp, "builder", "consecutive_failure_threshold",
            DEF_CONSECUTIVE_FAILURE_THRESHOLD, mode="int")
        opts.logfile = _get_conf(
            cp, "backend", "logfile", "/var/log/copr/backend.log")
        opts.error_logfile = _get_conf(
            cp, "backend", "error_logfile", "/var/log/copr/backend_error.log")
        opts.verbose = _get_conf(
            cp, "backend", "verbose", False, mode="bool")
        opts.worker_logdir = _get_conf(
            cp, "backend", "worker_logdir", "/var/log/copr/workers/")
        opts.terminate_vars = _get_conf(cp, "backend", "terminate_vars", "").split(",")

        opts.prune_days = _get_conf(cp, "backend", "prune_days", None, mode="int")
        opts.prune_script = _get_conf(cp, "backend", "prune_script", None, mode="path")

        opts.spawn_in_advance = _get_conf(
            cp, "backend", "spawn_in_advance", False, mode="bool")

        # ssh options
        opts.ssh = Bunch()
        # TODO: ansible Runner show some magic bugs with transport "ssh", using paramiko
        opts.ssh.transport = _get_conf(
            cp, "ssh", "transport", "paramiko")

        # thoughts for later
        # ssh key for connecting to builders?
        # cloud key stuff?
        #
        return opts


def get_auto_createrepo_status(front_url, username, projectname):
    client = CoprClient(copr_url=front_url)
    result = client.get_project_details(projectname, username)

    if "auto_createrepo" in result.data["detail"]:
        return bool(result.data["detail"]["auto_createrepo"])
    else:
        return True


def log(lf, msg, quiet=None):
    if lf:
        now = datetime.datetime.utcnow().isoformat()
        try:
            with open(lf, "a") as lfh:
                fcntl.flock(lfh, fcntl.LOCK_EX)
                lfh.write(str(now) + ":" + msg + "\n")
                fcntl.flock(lfh, fcntl.LOCK_UN)
        except (IOError, OSError) as e:
            sys.stderr.write(
                "Could not write to logfile {0} - {1}\n".format(lf, str(e)))
    if not quiet:
        print(msg)


def register_build_result(opts=None, failed=False):
    """
    Remember fails to redis.
    Successful build resets counter to zero.

    :param opts: BackendConfig, when opts not provided default config location will be used
    :param boolean failed: failure flag
    :param str origin: name of component produced failure, default: `builder`
    """
    if opts is None:
        opts = BackendConfigReader().read()

    # TODO: add config options to specify redis host, port
    conn = StrictRedis()  # connecting to default local redis instance

    key = CONSECUTIVE_FAILURE_REDIS_KEY
    if not failed:
        conn.set(key, 0)
    else:
        conn.incr(key)


def get_redis_connection(opts):
    # TODO: use host/port from opts
    kwargs = {}
    if hasattr(opts, "redis_db"):
        kwargs["db"] = opts.redis_db
    return StrictRedis(**kwargs)


def format_tb(ex, ex_traceback):
    tb_lines = traceback.format_exception(ex.__class__, ex, ex_traceback)
    return ''.join(tb_lines)
