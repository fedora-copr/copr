import logging
import munch
import subprocess
import rpm
import glob
import os
import re
import shutil

log = logging.getLogger("__main__")


class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


def run_cmd(cmd, cwd=".", preexec_fn=None):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str cwd: In which directory to execute the command
    :param func preexec_fn: a callback invoked before exec in subprocess

    :raises PackageImportException
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, preexec_fn=preexec_fn)
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RuntimeError(str(e))

    result = munch.Munch(
        cmd=cmd,
        stdout=stdout.decode(encoding='utf-8').strip(),
        stderr=stderr.decode(encoding='utf-8').strip(),
        returncode=process.returncode
    )
    log.debug(result)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


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


def locate_extra_content(dirpath, exclude):
    extra_content = []
    for path in glob.glob(os.path.join(dirpath, '*')):
        if path not in exclude:
            extra_content.append(path)
    return extra_content


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
        log.debug("Could not parse {} with error {}. Trying manual parsing."
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
            "Got invalid package package name '{}' from {}.".format(package_name, spec_path))

    return package_name


def get_pkg_evr(spec_path):
    try:
        rpm.addMacro('dist', '')
        pkg_info = get_rpm_spec_info(spec_path)
    except RpmSpecParseException as e:
        return ''
    finally:
        rpm.reloadConfig()

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
def munge_spec(spec_file, commit_id, commit_count, tgz_filename=None):
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


def prepare_test_spec(source_spec_path, target_spec_path, repo_path, package_name, commit_id='HEAD'):
    """
    Save modified spec file under target_spec_path.
    """
    latest_package_tag = get_latest_package_tag(
        package_name, repo_path, commit_id)

    if latest_package_tag:
        start_commit_id = run_cmd([
            'git', '-C', repo_path,
            'rev-list', latest_package_tag,
            '--max-count=1']).stdout
    else:
        start_commit_id = run_cmd([
            'git', '-C', repo_path,
            'rev-list', commit_id,
            '--max-parents=0']).stdout

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

    munge_spec(
        target_spec_path,
        commit_hex,
        commit_count,
        tgz_filename,
    )


def get_latest_package_tag(package_name, repo_path, from_commit_id='HEAD'):
    tag = None
    try:
        tag = run_cmd([
            'git', '-C', repo_path,
            'describe', from_commit_id,
            '--tags',
            '--match', package_name+'*',
            '--abbrev=0']).stdout
    except RunCommandException as e:
        log.warning('No tag found.')

    return tag
