""" helpers for Copr BDD tests """

from contextlib import contextmanager
import io
import json
import shlex
import subprocess
import sys
from urllib.parse import urlparse


@contextmanager
def no_output():
    """
    Suppress stdout/stderr when it is not captured by behave
    https://github.com/behave/behave/issues/863
    """
    real_out = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    yield
    sys.stdout, sys.stderr = real_out


def quoted_cmd(cmd):
    """ shell quoted cmd array as string """
    return " ".join(shlex.quote(arg) for arg in cmd)


def run(cmd):
    """
    Return exitcode, stdout, stderr.  It's bad there's no such thing in behave
    directly.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = process.communicate()
    print("Command exit status {} in: {}".format(
        process.returncode,
        quoted_cmd(cmd),
    ))
    if stdout:
        print("stdout:")
        print(stdout)
    if stderr:
        print("stderr:")
        print(stderr)
    return process.returncode, stdout, stderr


def run_check(cmd):
    """
    run() wrapper with assert on non-zero exit status
    """
    rc, out, err = run(cmd)
    assert rc == 0
    return out, err


class CoprCli:
    """ shortcut for copr --config <config> """
    def __init__(self, context):
        self.context = context

    @property
    def _base(self):
        return ["copr", "--config", self.context.copr_cli_config]

    def run(self, args):
        """
        Run any cli command.
        """
        rc, out, err = run(self._base + args)
        if rc:
            print(err)
        return rc, out, err

    def run_build(self, args):
        """
        Start build on background, and return build-id
        """
        cmd = self._base + args + ["--nowait"]
        (out, err) = run_check(cmd)
        for line in out.splitlines():
            if not line.startswith("Created builds: "):
                continue
            _, _, build_id = line.split(" ")
            build_id = int(build_id)
            self.context.builds.append(build_id)
            return build_id
        print("stderr:")
        print(err)
        raise RuntimeError("can't create build")

    def wait_build(self, build_id):
        """ Wait for the build to finish """
        cmd = self._base + ["watch-build", str(build_id)]
        return run(cmd)

    def wait_success_build(self, build_id):
        """ Wait for a successful build to finish """
        cmd = self._base + ["watch-build", str(build_id)]
        return run_check(cmd)

    def whoami(self):
        """ get the currently configured user name """
        out, _ = run_check(self._base + ["whoami"])
        return out.strip()

    def dnf_copr_project(self, owner, project):
        """ Get the ID we can `dnf copr enable` easily """
        host = urlparse(self.context.frontend_url).hostname
        return "{}/{}/{}".format(host, owner, project)

    def get_latest_pkg_builds(self, owner, project):
        """ Get the list of <name>-<version> strings inside copr from builds """
        cmd = self._base + ["list-packages", "{}/{}".format(owner, project),
                            "--with-latest-build"]
        out, _ = run_check(cmd)
        print("list-packages output:")
        print(out)
        packages = []
        for package in json.loads(out):
            found_package = package['name']
            if package.get('latest_build'):
                version = package['latest_build']['source_package']['version']
                # version has '-RELEASE' suffix
                version = version.split('-')[0]
                packages.append(found_package + "-" + version)
                continue
            packages.append(found_package)
        print("Found packages: {}".format(" ".join(packages)))
        return packages

    def get_package_builds(self, owner, project, package):
        """ Get the list of builds for given package """
        cmd = self._base + ["get-package", "{}/{}".format(owner, project),
                            "--name", package, "--with-all-builds"]
        out, _ = run_check(cmd)
        return json.loads(out)["builds"]


def assert_is_subset(set_a, set_b):
    """ assert that SET_A is subset of SET_B """
    if set_a.issubset(set_b):
        return
    raise AssertionError("Set {} is not a subset of {}".format(set_a, set_b))
