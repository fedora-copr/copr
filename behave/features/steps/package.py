"""
Steps that create Copr packages
"""

import json

from hamcrest import assert_that, equal_to

from behave import when, then  # pylint: disable=no-name-in-module


@when(u'a DistGit {distgit} "{package}" package from '
      u'{committype} "{commit}" is added')
def step_impl(context, distgit, package, committype, commit):
    _unused = committype
    distgit = distgit.strip().lower()
    status, _, _ = context.cli.run([
        'add-package-distgit', '--distgit', distgit, '--name', package,
        '--commit', commit, context.last_project_name])
    context.last_package_name = package
    assert status == 0

@when(u'the DistGit package is modified to build from {committype} "{commit}"')
def step_impl(context, committype, commit):
    _unused = committype
    # a relatively easy package from non-default branch
    status, _, _ = context.cli.run([
        'edit-package-distgit', '--distgit', 'centos', '--name',
        context.last_package_name, '--commit', commit,
        context.last_project_name])
    assert status == 0

@then(u'the package is configured to build from distgit {committype} "{commit}"')
def step_impl(context, committype, commit):
    _unused = committype
    package = context.last_package_name
    status, out, _ = context.cli.run(['get-package', context.last_project_name,
                                      '--name', package])
    assert not status
    package_info = json.loads(out)
    assert package_info['source_type'] == "distgit"
    assert_that(
        package_info['source_dict'],
        equal_to({
            "clone_url": "https://git.centos.org/rpms/{}.git".format(package),
            "committish": commit, "distgit": "centos",
        }))
