import json
import logging
import logging.handlers
import optparse
import os
import sys
import errno
import time
import types
import glob

import configparser
from configparser import ConfigParser

from contextlib import contextmanager
from operator import methodcaller

import traceback

from datetime import datetime
from threading import Thread

import subprocess

import pytz

import munch
from munch import Munch

from redis import StrictRedis

from copr.v3 import Client
from copr_backend.constants import DEF_BUILD_USER, DEF_BUILD_TIMEOUT, DEF_CONSECUTIVE_FAILURE_THRESHOLD, \
    CONSECUTIVE_FAILURE_REDIS_KEY, default_log_format
from copr_backend.exceptions import CoprBackendError, CoprBackendSrpmError

from . import constants


def pyconffile(filename):
    """
    Load python file as configuration file, inspired by python-flask
    "from_pyfile()
    """
    d = types.ModuleType('bus_config({0})'.format(filename))
    d.__file__ = filename
    try:
        with open(filename) as config_file:
            exec(compile(config_file.read(), filename, 'exec'), d.__dict__)
    except IOError as e:
        e.strerror = 'Unable to load configuration file (%s)' % e.strerror
        raise
    return d


def cmd_debug(cmd, rc, out, err, log):
    log.info("cmd: {}".format(cmd))
    log.info("rc: {}".format(rc))
    log.info("stdout: {}".format(out))
    log.info("stderr: {}".format(err))


def run_cmd(cmd, shell=False):
    """Runs given command in a subprocess.

    Params
    ------
    cmd: list(str) or str if shell==True
        command to be executed and its arguments
    shell: bool
        if the command should be interpreted by shell

    Returns
    -------
    munch.Munch(stdout, stderr, returncode)
        executed cmd, standard output, error output, and the return code
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell, encoding="utf-8")
    (stdout, stderr) = process.communicate()

    return munch.Munch(
        cmd=cmd,
        stdout=stdout,
        stderr=stderr,
        returncode=process.returncode
    )


def wait_log(log, reason="I don't know why.", timeout=5):
    """
    We need to wait a while, this should happen only when copr converges to
    boot-up/restart/..
    """
    if not log:
        return
    log.warning("I'm waiting {0}s because: {1}".format(timeout, reason))
    time.sleep(timeout)


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


def _get_limits_conf(parser):
    err1 = ("Unexpected format of 'builds_max_workers_arch' configuration "
            "option.  Please use format: "
            "builds_max_workers_arch = ARCH1=COUNT,ARCH2=COUNT")
    err2 = ("Duplicate arch {} in 'builds_max_workers_arch' configuration")
    limits = {"arch": {},}

    raw = _get_conf(parser, "backend", "builds_max_workers_arch", None)
    if raw:
        raw_arches = raw.split(',')
        for arch_spec in raw_arches:
            try:
                arch, count = arch_spec.split("=")
                arch = arch.strip()
                count = int(count.strip())
                if not arch or not count:
                    raise CoprBackendError("Empty builds_max_workers_arch spec")
                if arch in limits["arch"]:
                    raise CoprBackendError(err2.format(arch))
                limits["arch"][arch] = count
            except ValueError:
                raise CoprBackendError(err1)

    limits['sandbox'] = _get_conf(
        parser, "backend", "builds_max_workers_sandbox", 10, mode="int")
    limits['owner'] = _get_conf(
        parser, "backend", "builds_max_workers_owner", 20, mode="int")
    return limits


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

        except configparser.Error as e:
            raise CoprBackendError(
                "Error parsing config file: {0}: {1}".format(
                    self.config_file, e))

    def _read_unsafe(self):
        cp = ConfigParser()
        cp.read(self.config_file)

        opts = Munch()

        opts.results_baseurl = _get_conf(
            cp, "backend", "results_baseurl", "http://copr-be")

        opts.frontend_base_url = _get_conf(
            cp, "backend", "frontend_base_url", "http://copr-fe")

        opts.frontend_auth = _get_conf(
            cp, "backend", "frontend_auth", "PASSWORDHERE")

        opts.redis_host = _get_conf(
            cp, "backend", "redis_host", "127.0.0.1")

        opts.redis_port = _get_conf(
            cp, "backend", "redis_port", "6379")

        opts.redis_db = _get_conf(
            cp, "backend", "redis_db", "0")

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
                "max_vm_total": _get_conf(
                    cp, "backend", "group{}_max_vm_total".format(group_id),
                    # default=16, mode="int"),
                    default=8, mode="int"),
                "max_vm_per_user": _get_conf(
                    cp, "backend", "group{}_max_vm_per_user".format(group_id),
                    default=4, mode="int"),
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
                "playbook_timeout": _get_conf(
                    cp, "backend", "group{}_playbook_timeout".format(group_id),
                    default=None, mode="int"),
            }
            opts.build_groups.append(group)

        opts.vm_cycle_timeout = _get_conf(
            cp, "backend", "vm_cycle_timeout",
            default=10, mode="int")
        opts.vm_ssh_check_timeout = _get_conf(
            cp, "backend", "vm_ssh_check_timeout",
            default=5, mode="int")

        opts.destdir = _get_conf(cp, "backend", "destdir", None, mode="path")

        opts.fedmsg_enabled = _get_conf(
            cp, "backend", "fedmsg_enabled", False, mode="bool")
        opts.sleeptime = _get_conf(
            cp, "backend", "sleeptime", 5, mode="int")
        opts.timeout = _get_conf(
            cp, "builder", "timeout", DEF_BUILD_TIMEOUT, mode="int")
        opts.consecutive_failure_threshold = _get_conf(
            cp, "builder", "consecutive_failure_threshold",
            DEF_CONSECUTIVE_FAILURE_THRESHOLD, mode="int")

        opts.resalloc_connection = _get_conf(
            cp, "backend", "resalloc_connection", "http://localhost:49100")
        opts.builds_max_workers = _get_conf(
            cp, "backend", "builds_max_workers",
            default=60, mode="int")
        opts.builds_limits = _get_limits_conf(cp)

        opts.actions_max_workers = _get_conf(
            cp, "backend", "actions_max_workers",
            default=10, mode="int")

        opts.prune_workers = _get_conf(
            cp, "backend", "prune_workers",
            default=None, mode="int")

        opts.log_dir = _get_conf(
            cp, "backend", "log_dir", "/var/log/copr-backend/")
        opts.log_level = _get_conf(
            cp, "backend", "log_level", "info")
        opts.log_format = _get_conf(
            cp, "backend", "log_format", default_log_format)

        opts.prune_days = _get_conf(cp, "backend", "prune_days", None, mode="int")

        # ssh options
        opts.ssh = Munch()
        opts.ssh.builder_config = _get_conf(
            cp, "ssh", "builder_config", "/home/copr/.ssh/builder_config")

        opts.msg_buses = []
        for bus_config in glob.glob('/etc/copr/msgbuses/*.conf'):
            opts.msg_buses.append(pyconffile(bus_config))

        # thoughts for later
        # ssh key for connecting to builders?
        # cloud key stuff?
        #
        return opts


def uses_devel_repo(front_url, username, projectname):
    client = Client({"copr_url": front_url})
    project = client.project_proxy.get(username, projectname)
    return project.devel_mode


def get_persistent_status(front_url, username, projectname):
    client = Client({"copr_url": front_url})
    project = client.project_proxy.get(username, projectname)
    return project.persistent


def get_auto_prune_status(front_url, username, projectname):
    client = Client({"copr_url": front_url})
    project = client.project_proxy.get(username, projectname)
    return project.auto_prune


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

    conn = get_redis_connection(opts)

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
    kwargs = {}
    if hasattr(opts, "redis_db"):
        kwargs["db"] = opts.redis_db
    if hasattr(opts, "redis_host"):
        kwargs["host"] = opts.redis_host
    if hasattr(opts, "redis_port"):
        kwargs["port"] = opts.redis_port

    return StrictRedis(encoding="utf-8", decode_responses=True, **kwargs)


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
        # copr specific semantics

        # Alternative to copy.deepcopy().  If we edit the original record
        # object, any other following log handler would get the modified
        # variant.
        record = logging.makeLogRecord(record.__dict__)

        record.who = self.who

        # First argument to 'log.exception()' should be 'str' type.  If it is
        # not, we need to convert it before using '%' operator below.
        record.msg = str(record.msg)

        # For the message arguments, it is better to expand them right now
        # instead of relying on method in json.dumps(..., default=default)
        # and even worse rely on it's reverse action in RedisLogHandler.
        record.msg = record.msg % record.args
        if record.exc_info:
            _, error, tb = record.exc_info
            record.msg += "\n" + format_tb(error, tb)

        # cleanup the hard to json.dumps() stuff
        record.exc_info = None
        record.exc_text = None
        record.args = ()

        try:
            self.rc.rpush(constants.LOG_REDIS_FIFO, json.dumps(record.__dict__))
        # pylint: disable=W0703
        except Exception as error:
            _, _, ex_tb = sys.exc_info()
            sys.stderr.write("Failed to publish log record to redis, {}"
                             .format(format_tb(error, ex_tb)))


def get_redis_logger(opts, name, who):
    logger = logging.getLogger(name)
    level = getattr(opts, 'log_level', 'debug')
    level = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(level)

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
            raise # re-raise exception if a different error occurred


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


def ensure_dir_exists(path, log):
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except OSError as e:
            log.exception(str(e))


def get_chroot_arch(chroot):
    return chroot.rsplit("-", 2)[2]


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

def pkg_name_evr(srpm_path):
    """
    Queries a package for its name and evr (epoch:version-release)
    """
    cmd = ['rpm', '-qp', '--nosignature', '--qf',
           '%{NAME} %{EPOCH} %{VERSION} %{RELEASE}', srpm_path]

    try:
        result = run_cmd(cmd)
    except OSError as e:
        raise CoprBackendSrpmError(str(e))

    if result.returncode != 0:
        raise CoprBackendSrpmError('Error querying srpm: %s' % result.stderr)

    try:
        name, epoch, version, release = result.stdout.split(" ")
    except ValueError as e:
        raise CoprBackendSrpmError(str(e))

    # Epoch is an integer or '(none)' if not set
    if epoch.isdigit():
        evr = "{}:{}-{}".format(epoch, version, release)
    else:
        evr = "{}-{}".format(version, release)

    return name, evr


def format_filename(name, version, release, epoch, arch, zero_epoch=False):
    if not epoch.isdigit() and zero_epoch:
        epoch = "0"
    if epoch.isdigit():
        return "{}-{}:{}-{}.{}".format(name, epoch, version, release, arch)
    return "{}-{}-{}.{}".format(name, version, release, arch)


def call_copr_repo(directory, devel=False, add=None, delete=None, timeout=None,
                   logger=None):
    """
    Execute 'copr-repo' tool, and return True if the command succeeded.
    """
    cmd = ["copr-repo", "--batched", directory]
    def subdirs(option, subdirs):
        args = []
        if not subdirs:
            return []
        for subdir in subdirs:
            if subdir is None:
                # this should never happen, but better to skip
                # this than kill some backend process
                continue
            args += [option, subdir]
        return args
    cmd += subdirs('--add', add)
    cmd += subdirs('--delete', delete)
    if devel:
        cmd += ['--devel']

    try:
        if logger:
            logger.info("Running %s", " ".join(cmd))
        return not subprocess.call(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False

def build_target_dir(build_id, package_name=None):
    build_id = int(build_id)
    if not package_name:
        return "{:08d}".format(build_id)
    return "{:08d}-{}".format(build_id, package_name)

def build_chroot_log_name(build_id, package_name=None):
    return 'build-{}.log'.format(build_target_dir(build_id, package_name))

def walk_limited(path, maxdepth=None, mindepth=None):
    """
    The same as os.walk(), except that we can control the returned values to
    minimal and maximal depth of traversed directories.  The maximum depth is
    also lowering I/O because we don't actually have to traverse whole tree of
    unused files.
    """
    for dirpath, dirnames, files in os.walk(path):
        raw_subpath = os.path.relpath(dirpath, path)
        subpath = os.path.normpath(raw_subpath)
        depth = 0
        if subpath != ".":
            depth = len(subpath.split(os.sep))
        old_dirnames = dirnames.copy()
        if maxdepth is not None and depth >= maxdepth:
            # Per help(os.walk), we don't want to go deeper:
            # ...
            # When topdown is true, the caller can modify the dirnames list
            # in-place (e.g., via del or slice assignment), and walk will only
            # recurse into the subdirectories whose names remain in dirnames;
            # ...
            del dirnames[:]
        if mindepth is None or depth >= mindepth:
            yield (dirpath, old_dirnames, files)
