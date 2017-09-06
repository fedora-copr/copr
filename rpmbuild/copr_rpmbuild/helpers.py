import logging
import munch
import subprocess


log = logging.getLogger("__main__")


class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


def run_cmd(cmd, cwd=".", raise_on_error=True, preexec_fn=None):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str workdir: In which directory to execute the command
    :param bool raise_on_error: if PackageImportException should be raised on error

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
