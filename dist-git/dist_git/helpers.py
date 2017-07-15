import os
import logging
import ConfigParser
import pipes
import subprocess
import rpm
import pyrpkg
import munch
import glob
import re
import string
import shutil
import fileinput

# todo: replace with munch, check availability in epel
from bunch import Bunch
from requests import get
from functools import wraps

log = logging.getLogger(__name__)

from exceptions import PackageImportException, FileDownloadException, RunCommandException, \
        RpmSpecParseException, PackageNameCouldNotBeObtainedException


def single_run(lock):
    """
    Decorator to be used if you want to ensure
    a function is not run in parallel from within
    multiple threads.

    :param lock: lock to be used for locking

    :returns: wrapped function
    """
    def upper_wrapper(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            with lock:
                return f(*args, **kwargs)
        return wrapper
    return upper_wrapper


class EnumType(type):
    def __call__(self, attr):
        if isinstance(attr, int):
            for k, v in self.vals.items():
                if v == attr:
                    return k
            raise KeyError("num {0} is not mapped".format(attr))
        else:
            return self.vals[attr]


# The same enum is also in frontend's helpers.py
class FailTypeEnum(object):
    __metaclass__ = EnumType
    vals = {"unset": 0,
            # General errors mixed with errors for SRPM URL/upload:
            "unknown_error": 1,
            "build_error": 2,
            "srpm_import_failed": 3,
            "srpm_download_failed": 4,
            "srpm_query_failed": 5,
            # Git and Tito errors:
            "tito_general_error": 30,
            "git_clone_failed": 31,
            "git_wrong_directory": 32,
            "git_checkout_error": 33,
            "srpm_build_error": 34,
           }


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
        cp = ConfigParser.ConfigParser()
        cp.read(self.config_file)

        opts = Bunch()

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

        opts.cgit_pkg_list_location = _get_conf(
            cp, "dist-git", "cgit_pkg_list_location", "/var/lib/copr-dist-git/cgit_pkg_list"
        )

        opts.lookaside_location = _get_conf(
            cp, "dist-git", "lookaside_location", "/var/lib/dist-git/cache/lookaside/pkgs/"
        )

        opts.mock_scm_chroot = _get_conf(
            cp, "dist-git", "mock_scm_chroot", "fedora-rawhide-x86_64"
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
        return opts


def extract_srpm(srpm_path, destination):
    """
    Extracts srpm content to the target directory.

    raises: CheckOutputError
    """
    cwd = os.getcwd()
    os.chdir(destination)
    log.debug('Extracting srpm')
    try:
        cmd = "rpm2cpio {path} | cpio -idmv".format(path=pipes.quote(srpm_path))
        subprocess.check_output(cmd, shell=True)
    finally:
        os.chdir(cwd)


def download_file(url, destination):
    """
    Downloads file from the specified URL to
    a given location.

    raises: FileDownloadError
    returns str: filesystem path to the downloaded file.
    """
    log.debug("Downloading {0}".format(url))
    try:
        log.info(url)
        r = get(url, stream=True, verify=False)
    except Exception as e:
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


def locate_sources(dirpath):
    path_matches = []
    for ext in pyrpkg.Commands.UPLOADEXTS:
        path_matches += glob.glob(os.path.join(dirpath, '*.'+ext))
    return filter(os.path.isfile, path_matches)


def locate_spec(dirpath):
    spec_path = None
    path_matches = glob.glob(os.path.join(dirpath, '*.spec'))
    for path_match in path_matches:
        if os.path.isfile(path_match):
            spec_path = path_match
            break
    if not spec_path:
        raise PackageImportException('No .spec found at {}'.format(dirpath))
    return spec_path


def run_cmd(cmd, cwd='.', raise_on_error=True):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str workdir: In which directory to execute the command
    :param bool raise_on_error: if PackageImportException should be raised on error

    :raises PackageImportException
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RunCommandException(str(e))

    result = munch.Munch(
        cmd = cmd,
        stdout = stdout.strip(),
        stderr = stderr.strip(),
        returncode = process.returncode
    )
    log.debug(result)

    if result.returncode != 0:
        raise RunCommandException(result.stderr)

    return result


def get_package_name(spec_path):
    """
    Obtain name of a package described by specfile
    at spec_path.

    :param str spec_path: path to a spec file

    :returns str: package name

    :raises PackageNameCouldNotBeObtainedException
    """
    ts = rpm.ts()

    try:
        rpm_spec = ts.parseSpec(spec_path)
    except ValueError as e:
        log.info("Could not parse {}".format(spec_path))
    else:
        return rpm.expandMacro("%{name}")

    # regular expression fallback
    with open(spec_path, 'r') as spec_file:
        pattern = re.compile('^name:\s*([a-zA-Z0-9-._+]*)$', re.IGNORECASE)
        for spec_line in spec_file.readlines():
            match = pattern.match(spec_line)
            if match:
                return match.group(1)

    raise PackageNameCouldNotBeObtainedException(
        "Could not get package name from {}.".format(spec_path))


def get_pkg_evr(spec_path):
    try:
        pkg_info = get_rpm_spec_info(spec_path)
    except RpmSpecParseException as e:
        return ''

    if pkg_info.epoch:
        return '{}:{}-{}'.format(
            pkg_info.epoch, pkg_info.version, pkg_info.release)

    return '{}-{}'.format(pkg_info.version, pkg_info.release)


def get_rpm_spec_info(spec_path):
    """
    Return information about an rpm package
    as read from a spec file.

    :param str spec_path: path to a spec file

    :returns Munch: info about a package

    :raises RpmSpecParseException
    """
    ts = rpm.ts()

    try:
        rpm_spec = ts.parseSpec(spec_path)
        name = rpm.expandMacro("%{name}")
        version = rpm.expandMacro("%{version}")
        release = rpm.expandMacro("%{release}")
        epoch = rpm.expandMacro("%{epoch}")
        if epoch == "%{epoch}":
            epoch = None
    except ValueError as e:
        raise RpmSpecParseException(str(e))

    return munch.Munch(
        name=name,
        version=version,
        release=release,
        epoch=epoch,
        sources=rpm_spec.sources
    )


# origin: https://github.com/dgoodwin/tito/blob/e153a58611fc0cd198e9ae40c1033e51192a94a1/src/tito/common.py#L682
def munge_specfile(spec_file, commit_id, commit_count, tgz_filename=None):
    # If making a test rpm we need to get a little crazy with the spec
    # file we're building off. (Note we are modifying a temp copy of the
    # spec) Swap out the actual release for one that includes the git
    # SHA1 we're building for our test package.
    sha = commit_id[:7]

    for line in fileinput.input(spec_file, inplace=True):
        m = re.match(r'^(\s*Release:\s*)(.+?)(%{\?dist})?\s*$', line)
        if m:
            print('%s%s.git.%s.%s%s' % (
                m.group(1),
                m.group(2),
                commit_count,
                sha,
                m.group(3),
            ))
            continue

        m = re.match(r'^(\s*Source0?):\s*(.+?)$', line)
        if tgz_filename and m:
            print('%s: %s' % (m.group(1), tgz_filename))
            continue

        print(line.rstrip('\n'))


def setup_test_specfile(source_spec_path, target_spec_path, repo_path, package_name, commit_id='HEAD'):
    """
    Save modified spec file under target_spec_path.
    """
    try:
        latest_package_tag = get_latest_package_tag(
            package_name, repo_path, commit_id)
    except RunCommandException:
        start_commit_id = run_cmd([
            'git', '-C', repo_path,
            'rev-list', commit_id,
            '--max-parents=0']).stdout
    else:
        start_commit_id = run_cmd([
            'git', '-C', repo_path,
            'rev-list', latest_package_tag,
            '--max-count=1']).stdout

    commit_count_range = '{}..{}'.format(
        start_commit_id, commit_id)

    commit_count = run_cmd([
        'git', '-C', repo_path,
        'rev-list', commit_count_range,
        '--count']).stdout

    commit_hex = run_cmd([
        'git', '-C', repo_path,
        'rev-list', commit_id,
        '--max-count=1']).stdout

    tag = "git-{}.{}".format(commit_count, commit_hex[:7])
    tgz_filename = "{}-{}.tar.gz".format(package_name, tag)

    try:
        shutil.copy(source_spec_path, target_spec_path)
    except IOError as e:
        raise PackageImportException(str(e))

    munge_specfile(
        target_spec_path,
        commit_hex,
        commit_count,
        tgz_filename,
    )


def get_latest_package_tag(package_name, repo_path, from_commit_id='HEAD'):
    return run_cmd([
        'git', '-C', repo_path,
        'describe', from_commit_id,
        '--tags',
        '--match', package_name+'*',
        '--abbrev=0']).stdout
