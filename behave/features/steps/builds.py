"""
Steps related to Copr builds
"""

import random
from hamcrest import assert_that, equal_to, contains_string
from behave import when, then  # pylint: disable=no-name-in-module

from copr_behave_lib import run_check, run, assert_is_subset


@when(u'a build of {distgit} DistGit {package_name} package from '
      u'{committish} {committish_type} is done')
def step_impl(context, distgit, package_name, committish, committish_type):
    _ = (committish_type)
    distgit = distgit.lower()
    build = context.cli.run_build([
        "build-distgit",
        "--name", package_name,
        "--distgit", distgit,
        "--commit", committish,
        context.last_project_name,
    ])
    context.cli.wait_success_build(build)


@then(u'the build results are distributed')
def step_impl(context):
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
            "--qf", "%{NAME}-%{VERSION}", "--noplugins",
        ])
        packages_found = set(out.strip().splitlines())
        assert_is_subset(packages, packages_found)
    finally:
        # do the tests
        run(['sudo', 'dnf', 'copr', 'remove', project_id])


@then("there's a package {package} build with source version-release {vr} (without dist tag)")
def step_impl(context, package, vr):
    owner = context.cli.whoami()
    project = context.last_project_name
    found = False
    for build in context.cli.get_package_builds(owner, project, package):
        if build["source_package"]["version"] == vr:
            found = True
            break
    assert_that(found, equal_to(True))


@then('package changelog for {package_name} in {chroot} chroot contains "{string}" string')
def step_impl(context, package_name, chroot, string):
    owner = context.cli.whoami()
    project = context.last_project_name
    repo_id = "hell-{}".format(random.random())
    repo_url = "/".join([context.backend_url, "results", owner, project, chroot])
    repoquery = [
        "dnf", "repoquery", "--disablerepo=*", "--enablerepo", repo_id,
        "--repofrompath", "{},{}".format(repo_id, repo_url)
    ]

    out, _ = run_check(repoquery + ["--changelog", package_name])
    assert_that(out, contains_string(string))


@when(u'the package build is requested')
def step_impl(context):
    build = context.cli.run_build([
        "build-package",
        "--name", context.last_package_name,
        context.last_project_name,
    ])
    context.cli.wait_success_build(build)


@when(u'build of {distgit} DistGit namespaced {package_name} package from '
      u'{committish} {committish_type} in {namespace} is done')
def step_build_from_fork(context, distgit, package_name, committish, committish_type, namespace):
    _ = (committish_type)
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
