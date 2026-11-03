"""
Steps related to Copr builds
"""

import filecmp
import glob
import json
import os
import random
import shlex
import shutil
import tempfile
from hamcrest import assert_that, equal_to, contains_string
from behave import when, then  # pylint: disable=no-name-in-module

from copr_behave_lib import run_check, run, assert_is_subset


# pylint: disable=missing-function-docstring

@when('a build of {distgit} DistGit {package_name} package from '
      '{committish} {committish_type} is done')
def step_build_distgit(context, distgit, package_name, committish, committish_type):
    _ = committish_type
    distgit = distgit.lower()
    build = context.cli.run_build([
        "build-distgit",
        "--name", package_name,
        "--distgit", distgit,
        "--commit", committish,
        context.last_project_name,
    ])
    context.cli.wait_success_build(build)


@then('the build results are distributed')
def step_check_repo(context):
    # TODO: can we run this in container, and not rely on root access?
    owner = context.cli.whoami()
    project = context.last_project_name
    project_id = context.cli.dnf_copr_project(owner, project)
    packages = set(context.cli.get_latest_pkg_builds(owner, project))
    try:
        run_check(['sudo', 'dnf', '-y', 'copr', 'enable', project_id])
        (out, _) = run_check([
            "sudo", "dnf", "repoquery", "--disablerepo=*",
            "--enablerepo=*{}*".format(project), "--available",
            "--qf", "%{NAME}-%{VERSION}\n", "--noplugins",
        ])
        packages_found = set(out.strip().splitlines())
        assert_is_subset(packages, packages_found)
    finally:
        # do the tests
        run(['sudo', 'dnf', 'copr', 'remove', project_id])


@then("there's a package {package} build with source version-release {vr} (without dist tag)")
def step_nevra_presence(context, package, vr):
    owner = context.cli.whoami()
    project = context.last_project_name
    found = False
    for build in context.cli.get_package_builds(owner, project, package):
        if build["source_package"]["version"] == vr:
            found = True
            break
    assert_that(found, equal_to(True))


@then('package changelog for {package_name} in {chroot} chroot contains "{string}" string')
def step_check_changelog_content(context, package_name, chroot, string):
    owner = context.cli.whoami()
    project = context.last_project_name
    repo_id = "hell-{}".format(random.random())
    repo_url = "/".join([context.content_url, owner, project, chroot])
    repoquery = [
        "dnf", "repoquery", "--disablerepo=*", "--enablerepo", repo_id,
        "--repofrompath", "{},{}".format(repo_id, repo_url)
    ]

    out, _ = run_check(repoquery + ["--changelogs", package_name])
    assert_that(out, contains_string(string))


@when('the package build is requested')
def step_rebuild_pkg(context):
    build = context.cli.run_build([
        "build-package",
        "--name", context.last_package_name,
        context.last_project_name,
    ])
    context.cli.wait_success_build(build)


@when('build of {distgit} DistGit namespaced {package_name} package from '
      '{committish} {committish_type} in {namespace} is done')
def step_build_from_fork(context, distgit, package_name, committish, committish_type, namespace):
    _ = committish_type
    distgit = distgit.lower()
    build = context.cli.run_build([
        "build-distgit",
        "--name", package_name,
        "--distgit", distgit,
        "--commit", committish,
        "--namespace", namespace,
        context.last_project_name,
    ])
    context.cli.wait_success_build(build)


@when('build of {distgit} DistGit {package_name} package from {committish} '
      '{committish_type} from fork clone url "{clone_url}" is done')
def step_build_from_fork_clone_url(context, distgit, package_name,
                                   committish, committish_type, clone_url):
    _ = committish_type
    distgit = distgit.lower()
    build = context.cli.run_build([
        "build-distgit",
        "--name", package_name,
        "--distgit", distgit,
        "--commit", committish,
        "--clone-url", clone_url,
        context.last_project_name,
    ])
    context.last_distgit_package_name = package_name
    context.cli.wait_success_build(build)


def _last_build_srpm_url(context):
    """
    Return the source RPM URL of the last requested build.
    """
    owner = context.cli.whoami()
    project = context.last_project_name
    package = context.last_distgit_package_name
    build_id = context.builds[-1]
    for build in context.cli.get_package_builds(owner, project, package):
        if build["id"] == build_id:
            return build["source_package"]["url"]
    raise RuntimeError("build {} not found".format(build_id))


@then('the source RPM of the last build contains the same specfile as '
      '"{clone_url}"')
def step_check_srpm_specfile(context, clone_url):
    """
    Check that the spec file inside the source RPM of the last build is
    identical to the spec file in the given (fork) git repository, so
    we know the package was built from the requested sources.
    """
    srpm_url = _last_build_srpm_url(context)

    if not shutil.which("cpio"):
        run_check(["sudo", "dnf", "-y", "install", "cpio"])

    with tempfile.TemporaryDirectory() as tmp_dir:
        srpm = os.path.join(tmp_dir, "source-rpm.rpm")
        run_check(["curl", "--fail", "--silent", "--show-error",
                   "--output", srpm, srpm_url])

        out, _ = run_check([
            "rpm", "-qp", "--qf", "%{NEVRA}", srpm])
        print("Downloaded source RPM: {} ({})".format(out, srpm_url))

        # extract the spec file from the source RPM
        srpm_dir = os.path.join(tmp_dir, "srpm")
        os.makedirs(srpm_dir)
        run_check(["bash", "-c",
                   "cd {0} && rpm2cpio {1} | cpio -im --quiet".format(
                       shlex.quote(srpm_dir), shlex.quote(srpm))])
        specs = glob.glob(os.path.join(srpm_dir, "*.spec"))
        assert len(specs) == 1, "one spec file expected in {}".format(srpm_dir)

        # get the spec file from the forked repository
        fork_dir = os.path.join(tmp_dir, "fork")
        run_check(["git", "clone", "--quiet", "--depth", "1",
                   clone_url, fork_dir])
        fork_specs = glob.glob(os.path.join(fork_dir, "*.spec"))
        assert len(fork_specs) == 1, \
            "one spec file expected in {}".format(fork_dir)

        assert filecmp.cmp(specs[0], fork_specs[0], shallow=False), \
            "spec file in {} differs from {}".format(specs[0], fork_specs[0])


@when('a build from specfile template "{template}" is done')
def step_build_from_spec_template(context, template):
    """
    Take a specfile from templates/ directory, and build it.
    """
    path = os.path.join("templates", template)

    def _replace(string):
        string = string.replace('@FEDORA_LATEST@',
                                str(context.cli.get_latest_fedora_chroot()))
        return string

    with open(path, "r", encoding="utf-8") as template_fd:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, template), "w", encoding="utf-8") as temp_spec:
                for line in template_fd.readlines():
                    temp_spec.write(_replace(line))
                temp_spec.flush()
                build = context.cli.run_build(["build", context.last_project_name,
                                               temp_spec.name])
                context.cli.wait_success_build(build)


@then('the package "{package_name}" should have "{state}" state for "{chroots}" chroots')
def step_check_monitor_status(context, package_name, state, chroots):
    """
    Check that a subset of build.chroots ended-up in a desired state.
    """
    chroots = [x.strip() for x in chroots.split(",")]
    _, output, _ = context.cli.run(["monitor", context.last_project_name])
    data = json.loads(output)
    for chroot in chroots:
        if "-latest-" in chroot:
            chroot = chroot.replace("latest",
                                    str(context.cli.get_latest_fedora_chroot()))
        found = False
        for result in data:
            if result["name"] != package_name:
                continue
            if result["chroot"] != chroot:
                continue
            found = True
            assert result["state"] == state
            break
        assert found
