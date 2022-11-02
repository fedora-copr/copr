import os
import sys
import logging
import subprocess
import munch

from oslo_concurrency import lockutils
from setproctitle import getproctitle, setproctitle
from copr_common.request import SafeRequest, RequestError
from munch import Munch
from .exceptions import FileDownloadException, RunCommandException

from contextlib import contextmanager
from configparser import ConfigParser

log = logging.getLogger(__name__)
LOCK_PATH = "/var/lock/copr-dist-git"


@contextmanager
def lock(name):
    """
    Create a lock file that can be accessed only by one thread at the time.
    A practical use-case for this is to lock a repository so multiple versions
    of the same package cannot be imported in paralel.
    """
    title = getproctitle()
    setproctitle("{0} [locking]".format(title))
    with lockutils.lock(name=name, external=True, lock_path=LOCK_PATH,
                        fair=True, delay=0):
        setproctitle("{0} [locked]".format(title))
        yield
    setproctitle(title)


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


class ConfigReaderError(Exception):
    pass


class ConfigReader(object):
    def __init__(self, config_file=None):
        self.config_file = config_file or "/etc/copr/copr-dist-git.conf"

    def read(self):
        try:
            opts = self._read_unsafe()
            return opts

        except ConfigParser.Error as e:
            raise ConfigReaderError(
                "Error parsing config file: {0}: {1}".format(
                    self.config_file, e))

    def _read_unsafe(self):
        cp = ConfigParser()
        cp.read(self.config_file)

        opts = Munch()

        opts.frontend_base_url = _get_conf(
            cp, "dist-git", "frontend_base_url", "http://copr-fe")

        opts.frontend_auth = _get_conf(
            cp, "dist-git", "frontend_auth", "PASSWORDHERE")

        opts.log_dir = _get_conf(
            cp, "dist-git", "log_dir", "/var/log/copr-dist-git"
        )

        opts.per_task_log_dir = _get_conf(
            cp, "dist-git", "per_task_log_dir", "/var/lib/copr-dist-git/per-task-logs"
        )

        opts.sleep_time = _get_conf(
            cp, "dist-git", "sleep_time", 15, mode="int"
        )

        # Whether to use multi-threaded dist-git or not
        # It might be useful to set False for debugging
        # while ipdb does not support multiple threads.
        opts.multiple_threads = _get_conf(
            cp, "dist-git", "multiple_threads", True, mode="bool"
        )

        opts.pool_busy_sleep_time = _get_conf(
            cp, "dist-git", "pool_busy_sleep_time", 0.5, mode="float"
        )

        # The Copr administrator is responsible for configuring /etc/cgitrc to
        # include this file.
        opts.cgit_cache_file = _get_conf(
            cp, "dist-git", "cgit_cache_file", "/var/cache/cgit/repo-configuration.rc"
        )

        opts.cgit_cache_list_file = _get_conf(
            cp, "dist-git", "cgit_cache_list_file", "/var/cache/cgit/repo-subdirs.list"
        )

        opts.cgit_cache_lock_file = _get_conf(
            cp, "dist-git", "cgit_cache_lock_file", "/var/cache/cgit/copr-repo.lock"
        )

        opts.lookaside_location = _get_conf(
            cp, "dist-git", "lookaside_location", "/var/lib/dist-git/cache/lookaside/pkgs/"
        )

        opts.git_base_url = _get_conf(
            cp, "dist-git", "git_base_url", "/var/lib/dist-git/git/%(module)s"
        )

        opts.git_user_name = _get_conf(
            cp, "dist-git", "git_user_name", "CoprDistGit"
        )

        opts.git_user_email = _get_conf(
            cp, "dist-git", "git_user_email", "copr-devel@lists.fedorahosted.org"
        )

        opts.max_workers = _get_conf(
            cp, "dist-git", "max_workers", default=10, mode="int"
        )

        opts.redis_host = _get_conf(cp, "dist-git", "redis_host", "localhost")
        opts.redis_port = _get_conf(cp, "dist-git", "redis_port", "6379")

        return opts


def download_file(url, destination):
    """
    Downloads file from the specified URL to
    a given location.

    raises: FileDownloadError
    returns str: filesystem path to the downloaded file.
    """
    log.debug("Downloading {0}".format(url))
    try:
        request = SafeRequest(log=log, timeout=10 * 60)
        r = request.send(url, method='get', stream=True)
    except RequestError as e:
        raise FileDownloadException(str(e))

    if 200 <= r.status_code < 400:
        try:
            filename = os.path.basename(url)
            filepath = os.path.join(destination, filename)
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
        except Exception as e:
            raise FileDownloadException(str(e))
    else:
        raise FileDownloadException("Failed to fetch: {0} with HTTP status: {1}"
                                    .format(url, r.status_code))
    return filepath


def run_cmd(cmd, cwd='.', raise_on_error=True):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str workdir: In which directory to execute the command
    :param bool raise_on_error: if RunCommandException should be raised on error

    :raises RunCommandException
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=cwd, encoding='utf-8')
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RunCommandException(str(e))

    result = munch.Munch(
        cmd=cmd,
        stdout=stdout.strip(),
        stderr=stderr.strip(),
        returncode=process.returncode
    )
    log.debug(result)

    if result.returncode != 0:
        raise RunCommandException(result.stderr)

    return result


def get_distgit_opts(path):
    """
    Return a parsed config file as a `dict`
    """
    config_reader = ConfigReader(path)

    if not os.path.exists(path):
        sys.stderr.write("No config file found at: {0}\n".format(path))
        sys.exit(1)

    return config_reader.read()
