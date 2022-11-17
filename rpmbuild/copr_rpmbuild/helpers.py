import errno
import logging
import subprocess
import glob
import os
import sys
import re
import configparser
import datetime
import shlex
from threading import Timer
from collections import OrderedDict
import rpm
import munch

from six.moves.urllib.parse import urlparse
from copr_common.enums import BuildSourceEnum


log = logging.getLogger("__main__")

CONF_DIRS = [os.getcwd(), "/etc/copr-rpmbuild"]


def cmd_debug(result):
    log.debug("")
    log.debug("cmd: {0}".format(result.cmd))
    log.debug("cwd: {0}".format(result.cwd))
    log.debug("rc: {0}".format(result.returncode))
    log.debug("stdout: {0}".format(result.stdout))
    log.debug("stderr: {0}".format(result.stderr))
    log.debug("")


def cmd_readable(cmd):
    return ' '.join([shlex.quote(part) for part in cmd])


def run_cmd(cmd, cwd=".", preexec_fn=None):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str cwd: In which directory to execute the command
    :param func preexec_fn: a callback invoked before exec in subprocess

    :raises RuntimeError
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    log.info('Running: ' + cmd_readable(cmd))

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, preexec_fn=preexec_fn)
        (stdout, stderr) = process.communicate()
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise RuntimeError(
                "Command '{0}' can not be executed.  Either the command "
                "itself isn't installed, or it's interpreter (shebang) is "
                "missing on the system".format(cmd[0]))
        raise RuntimeError(str(e))

    result = munch.Munch(
        cmd=cmd,
        stdout=stdout.decode('utf-8').strip(),
        stderr=stderr.decode('utf-8').strip(),
        returncode=process.returncode,
        cwd=cwd
    )
    cmd_debug(result)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


def locate_spec(dirpath):
    spec_path = None
    path_matches = glob.glob(os.path.join(dirpath, '*.spec'))
    for path_match in path_matches:
        if os.path.isfile(path_match):
            spec_path = path_match
            break
    if not spec_path:
        raise RuntimeError('No .spec found at {0}'.format(dirpath))
    return spec_path


def locate_srpm(dirpath):
    srpm_path = None
    path_matches = glob.glob(os.path.join(dirpath, '*.src.rpm'))
    for path_match in path_matches:
        if os.path.isfile(path_match):
            srpm_path = path_match
            break
    if not srpm_path:
        raise RuntimeError('No .src.rpm found at {0}'.format(dirpath))
    return srpm_path


def get_package_name(spec_path):
    """
    Obtain name of a package described by spec
    at spec_path.

    :param str spec_path: path to a spec file

    :returns str: package name

    :raises PackageNameCouldNotBeObtainedException
    """
    ts = rpm.ts()

    try:
        rpm_spec = ts.parseSpec(spec_path)
    except ValueError as e:
        log.debug("Could not parse {0} with error {1}. Trying manual parsing."
                 .format(spec_path, str(e)))

        with open(spec_path, 'r') as spec_file:
            spec_lines = spec_file.readlines()

        patterns = [
            re.compile(r'^(name):\s*(\S*)$', re.IGNORECASE),
            re.compile(r'^%global\s*(\S*)\s*(\S*)$'),
            re.compile(r'^%define\s*(\S*)\s*(\S*)$')]

        for spec_line in spec_lines:
            for pattern in patterns:
                match = pattern.match(spec_line)
                if not match:
                    continue
                rpm.addMacro(
                    match.group(1), match.group(2))

    package_name = rpm.expandMacro("%{name}")
    rpm.reloadConfig()

    if not re.match(r'[a-zA-Z0-9-._+]+', package_name):
        raise PackageNameCouldNotBeObtainedException(
            "Got invalid package package name '{0}' from {1}.".format(package_name, spec_path))

    return package_name


def string2list(string):
    return [elem.strip() for elem in re.split(r"\s*,\s*|\s+", string) if elem]


def read_config(config_path=None):
    config = configparser.RawConfigParser(defaults={
        "resultdir": "/var/lib/copr-rpmbuild/results",
        "workspace": "/var/lib/copr-rpmbuild/workspace",
        "lockfile": "/var/lib/copr-rpmbuild/lockfile",
        "logfile": "/var/lib/copr-rpmbuild/main.log",
        "pidfile": "/var/lib/copr-rpmbuild/pid",
        "logger_pidfile": "/var/lib/copr-rpmbuild/logger_pid",
        "enabled_source_protocols": "https ftps",
        "rpm_vendor_copr_name": "Unknown Copr",
    })
    config_paths = [os.path.join(path, "main.ini") for path in CONF_DIRS]
    config.read(config_path or reversed(config_paths))
    if not config.sections():
        log.error("No configuration file main.ini in: {0}".format(" ".join(CONF_DIRS)))
        sys.exit(1)
    return config


def path_join(*args):
    return os.path.normpath('/'.join(args))


def get_mock_uniqueext():
    """
    This is a hack/workaround not to reuse already setup
    chroot from a previous run but to always setup a new
    one. Upon key interrupt during build, mock chroot
    becomes further unuseable and there are also problems
    with method _fixup_build_user in mock for make_srpm
    method together with --private-users=pick for sytemd-
    nspawn.
    """
    return datetime.datetime.now().strftime('%s.%f')


def build_srpm(srcdir, destdir):
    cmd = [
        'rpmbuild', '-bs',
        '--define', '_sourcedir ' + srcdir,
        '--define', '_rpmdir '    + srcdir,
        '--define', '_builddir '  + srcdir,
        '--define', '_specdir '   + srcdir,
        '--define', '_srcrpmdir ' + destdir,
    ]

    specfiles = glob.glob(os.path.join(srcdir, '*.spec'))
    if len(specfiles) == 0:
        raise RuntimeError("no spec file available")

    if len(specfiles) > 1:
        raise RuntimeError("too many specfiles: {0}".format(
            ', '.join(specfiles)
        ))

    cmd += [specfiles[0]]
    run_cmd(cmd)


def copr_chroot_to_task_id(copr, chroot):
    copr_token = re.sub('@', 'group_', copr)
    copr_token = re.sub('/', '-', copr_token)
    return copr_token +'-'+chroot


def parse_copr_name(name):
    m = re.match(r"([^/]+)/(.*)", name)
    ownername = m.group(1)
    projectname = m.group(2)
    return ownername, projectname


def dump_live_log(logfile):
    filter_continuing_lines = "/usr/bin/copr-rpmbuild-loggify"
    tee_output = "tee -a {0}".format(shlex.quote(logfile))
    cmd = filter_continuing_lines + "|" + tee_output
    tee = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=True)
    os.dup2(tee.stdin.fileno(), sys.stdout.fileno())
    os.dup2(tee.stdin.fileno(), sys.stderr.fileno())
    return tee.pid


class GentlyTimeoutedPopen(subprocess.Popen):
    timers = []

    def __init__(self, cmd, timeout=None, **kwargs):
        log.info('Running (timeout={to}): {cmd}'.format(
            to=str(timeout),
            cmd=cmd_readable(cmd),
        ))

        super(GentlyTimeoutedPopen, self).__init__(cmd, **kwargs)
        if not timeout:
            return

        def timeout_cb(me, string, signal):
            log.error(" !! Copr timeout => sending {0}".format(string))
            me.send_signal(signal)

        delay = timeout
        for string, signal in [('INT', 2), ('TERM', 15), ('KILL', 9)]:
            timer = Timer(delay, timeout_cb, [self, string, signal])
            timer.start()
            self.timers.append(timer)
            delay = delay + 10

    def done(self):
        for timer in self.timers:
            timer.cancel()

def git_clone_url_basepath(clone_url):
    """
    Given the clone URL, get the last part of the URL, without the git suffix.
    """
    last_part = clone_url.rstrip("/").split("/")[-1]
    if last_part.endswith(".git"):
        return last_part[:-4]
    return last_part

def git_clone_and_checkout(url, committish, repo_path, scm_type="git"):
    """
    Clone given URL (SCM_TYPE=svn/git) into REPO_PATH, and checkout the
    COMMITTISH reference.
    """
    if scm_type == 'git':
        clone_cmd = ['git', 'clone', url,
                     repo_path, '--depth', '500',
                     '--no-single-branch',
                     "--recursive"]
    else:
        clone_cmd = ['git', 'svn', 'clone', url,
                     repo_path]

    try:
        run_cmd(clone_cmd)
    except RuntimeError as e:
        log.error(str(e))
        if scm_type == 'git':
            # re-try with deep-full clone
            run_cmd(['git', 'clone', url, repo_path])
        else:
            raise e

    if committish:
        # Do the checkout only if explicitly requested, otherwise build against
        # the default branch.

        # First, fetch a remote reference if used.
        # This is a guesstimate for GitHub, GitLab and Pagure.
        if committish.startswith("refs/"):
            fetch_cmd = ['git', 'fetch', 'origin', '{0}:{0}'.format(committish)]
            run_cmd(fetch_cmd, cwd=repo_path)

        checkout_cmd = ['git', 'checkout', committish]
        run_cmd(checkout_cmd, cwd=repo_path)


def macros_for_task(task, config):
    """
    Based on a task definition, generate RPM macros that should be defined in
    the buildroot. Macros are simply returned as a `dict` and it is up to the
    caller to pass them into Mock via `--define`, dump `~/.rpmmacros`, etc.

    Each macro is to be defined with %-sign at the begining.
    """
    # We use OdrderedDict just to be sure that we generate the macros in the
    # same order. It doesn't really matter in production, but is easier to test.
    macros = OrderedDict({
        "%copr_username": task["project_owner"],
        "%copr_projectname": task["project_name"],
    })

    rpm_vendor_copr_name = config.get("main", "rpm_vendor_copr_name", fallback=None)
    if rpm_vendor_copr_name:
        vendor = "{0} - {1} {2}".format(
            rpm_vendor_copr_name,
            "group" if task["project_owner"].startswith("@") else "user",
            task["project_owner"],
        )
        macros["%vendor"] = vendor

    task_id = task.get("task_id")
    if task_id:
        macros["%buildtag"] = ".copr" + re.sub("-.*", "", task_id)

    if is_srpm_build(task):
        macros["%dist"] = "%nil"
        macros["%_disable_source_fetch"] = "0"

    protocols_str = config.get("main", "enabled_source_protocols", fallback=None)
    if task["source_type"] != BuildSourceEnum.upload and protocols_str:
        protocols_list = string2list(protocols_str)
        protocols = ",".join(["+" + protocol for protocol in protocols_list])
        macros["%__urlhelper_localopts"] = "--proto -all,{0}".format(protocols)

    return macros


def is_srpm_build(task):
    """
    Return `True` if the `self.source_dict` belongs to a SRPM build task
    """
    return task.get("source_type") is not None
