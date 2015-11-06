from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
import json
import logging
import logging.handlers
from operator import methodcaller
import optparse
import ConfigParser
import os
import sys
import errno
from contextlib import contextmanager

import traceback

from datetime import datetime
import pytz
# from dateutil.parser import parse as dt_parse

from munch import Munch
from redis import StrictRedis
from . import constants

from copr.client import CoprClient
from backend.constants import DEF_BUILD_USER, DEF_BUILD_TIMEOUT, DEF_CONSECUTIVE_FAILURE_THRESHOLD, \
    CONSECUTIVE_FAILURE_REDIS_KEY, default_log_format
from backend.exceptions import CoprBackendError

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

def chroot_to_branch(chroot):
    """
    Get a git branch name from chroot. Follow the fedora naming standard.
    """
    os_name, version, _ = chroot.split("-")
    if os_name == "fedora":
        os_name = "f"
    elif os_name == "epel" and int(version) <= 6:
        os_name = "el"
    return "{}{}".format(os_name, version)

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

        opts = Munch()

        opts.results_baseurl = _get_conf(
            cp, "backend", "results_baseurl", "http://copr-be")

        opts.frontend_base_url = _get_conf(
            cp, "backend", "frontend_base_url", "http://copr-fe")

        opts.dist_git_url = _get_conf(
            cp, "backend", "dist_git_url", "http://dist-git")

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
                    default=8, mode="int"),
                "max_vm_per_user": _get_conf(
                    cp, "backend", "group{}_max_vm_per_user".format(group_id),
                    default=4, mode="int"),
                "max_builds_per_vm": _get_conf(
                    cp, "backend", "group{}_max_builds_per_vm".format(group_id),
                    default=10, mode="int"),
                "max_spawn_processes": _get_conf(
                    cp, "backend", "group{}_max_spawn_processes".format(group_id),
                    default=2, mode="int"),
                "vm_spawn_min_interval": _get_conf(
                    cp, "backend", "group{}_vm_spawn_min_interval".format(group_id),
                    default=30, mode="int"),
                "vm_dirty_terminating_timeout": _get_conf(
                    cp, "backend", "group{}_vm_dirty_terminating_timeout".format(group_id),
                    default=120, mode="int"),
                "vm_health_check_period": _get_conf(
                    cp, "backend", "group{}_vm_health_check_period".format(group_id),
                    default=120, mode="int"),
                "vm_health_check_max_time": _get_conf(
                    cp, "backend", "group{}_vm_health_check_max_time".format(group_id),
                    default=300, mode="int"),
                "vm_max_check_fails": _get_conf(
                    cp, "backend", "group{}_vm_max_check_fails".format(group_id),
                    default=2, mode="int"),
                "vm_terminating_timeout": _get_conf(
                    cp, "backend", "group{}_vm_terminating_timeout".format(group_id),
                    default=600, mode="int"),
            }
            opts.build_groups.append(group)

        opts.vm_cycle_timeout = _get_conf(
            cp, "backend", "vm_cycle_timeout",
            default=10, mode="int")
        opts.vm_ssh_check_timeout = _get_conf(
            cp, "backend", "vm_ssh_check_timeout",
            default=5, mode="int")

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
        opts.log_dir = _get_conf(
            cp, "backend", "log_dir", "/var/log/copr/")
        opts.log_level = _get_conf(
            cp, "backend", "log_level", "info")
        opts.verbose = _get_conf(
            cp, "backend", "verbose", False, mode="bool")

        opts.prune_days = _get_conf(cp, "backend", "prune_days", None, mode="int")

        # ssh options
        opts.ssh = Munch()
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


# def log(lf, msg, quiet=None):
#     if lf:
#         now = datetime.datetime.utcnow().isoformat()
#         try:
#             with open(lf, "a") as lfh:
#                 fcntl.flock(lfh, fcntl.LOCK_EX)
#                 lfh.write(str(now) + ":" + msg + "\n")
#                 fcntl.flock(lfh, fcntl.LOCK_UN)
#         except (IOError, OSError) as e:
#             sys.stderr.write(
#                 "Could not write to logfile {0} - {1}\n".format(lf, str(e)))
#     if not quiet:
#         print(msg)
#

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
    """
    Creates redis client object using backend config

    :rtype: StrictRedis
    """
    # TODO: use host/port from opts
    kwargs = {}
    if hasattr(opts, "redis_db"):
        kwargs["db"] = opts.redis_db
    if hasattr(opts, "redis_host"):
        kwargs["host"] = opts.redis_host
    if hasattr(opts, "redis_port"):
        kwargs["port"] = opts.redis_port

    return StrictRedis(**kwargs)


def format_tb(ex, ex_traceback):
    tb_lines = traceback.format_exception(ex.__class__, ex, ex_traceback)
    return ''.join(tb_lines)


class RedisPublishHandler(logging.Handler):
    """
    :type rc: StrictRedis
    """
    def __init__(self, rc, who, level=logging.NOTSET,):
        super(RedisPublishHandler, self).__init__(level)

        self.rc = rc
        self.who = who

    def emit(self, record):
        try:
            msg = record.__dict__
            msg["who"] = self.who

            if msg.get("exc_info"):
                # from celery.contrib import rdb; rdb.set_trace()
                _, error, tb = msg.pop("exc_info")
                msg["traceback"] = format_tb(error, tb)

            self.rc.publish(constants.LOG_PUB_SUB, json.dumps(msg))
        # pylint: disable=W0703
        except Exception as error:
            _, _, ex_tb = sys.exc_info()
            sys.stderr.write("Failed to publish log record to redis, {}"
                             .format(format_tb(error, ex_tb)))


def get_redis_logger(opts, name, who):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        rc = get_redis_connection(opts)
        handler = RedisPublishHandler(rc, who, level=logging.DEBUG)
        logger.addHandler(handler)

    return logger


def create_file_logger(name, filepath, fmt=None):
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.handlers.WatchedFileHandler(filename=filepath)
        handler.setFormatter(fmt if fmt is not None else default_log_format)
        logger.addHandler(handler)

    return logger


def utc_now():
    """
    :return datetime.datetime: Current utc datetime with specified timezone
    """
    u = datetime.utcnow()
    u = u.replace(tzinfo=pytz.utc)
    return u


def silent_remove(filename):
    try:
        os.remove(filename)
    except OSError as e: # this would be "except OSError, e:" before Python 2.6
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occured


def get_backend_opts():
    args = sys.argv[1:]
    parser = optparse.OptionParser("\ncopr-be [options]")
    parser.add_option("-c", "--config", default="/etc/copr/copr-be.conf",
                      dest="config_file",
                      help="config file to use for copr-be run")

    opts, args = parser.parse_args(args)
    if not os.path.exists(opts.config_file):
        sys.stderr.write("No config file found at: {0}\n".format(
            opts.config_file))
        sys.exit(1)

    config_file = os.path.abspath(opts.config_file)
    config_reader = BackendConfigReader(config_file, {})
    return config_reader.read()


@contextmanager
def local_file_logger(name, path, fmt):
    build_logger = create_file_logger(name, path, fmt)
    try:
        yield build_logger
    finally:
        # TODO: kind of ugly solution
        # we should remove handler from build loger, otherwise we would write
        # to the previous project
        for h in build_logger.handlers[:]:
            build_logger.removeHandler(h)
