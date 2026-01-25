"""
Steps that create Copr projects
"""

import os

from behave import given  # pylint: disable=no-name-in-module

from copr_behave_lib import no_output


def clean_project(context, project):
    """ Clean copr project by copr-cli """
    with no_output():
        rc, out, err = context.cli.run(["delete", project])
    if rc != 0:
        print("can not delete the project")
        if out:
            print("stdout:\n" + out)
        if err:
            print("stderr:\n" + err)
        assert AssertionError("cli returned {}".format(rc))


@given(u'a project that builds packages for this system')
def step_impl(context):
    name = context.scenario.name.replace(" ", "-").lower()
    name = "{}-{}".format(name, context.started)
    cmd = ["create", name, "--chroot", context.system_chroot]
    context.cli.run(cmd)
    context.add_cleanup(clean_project, context, name)
    context.last_project_name = name


@given(u'a project with {chroot} chroot enabled')
def step_impl(context, chroot):
    name = context.scenario.name.replace(" ", "-").lower()
    name = "{}-{}".format(name, context.started)
    cmd = ["create", name, "--chroot", chroot]
    context.cli.run(cmd)
    context.add_cleanup(clean_project, context, name)
    context.last_project_name = name


@given('a project with "{distributions}" distributions with "{architectures}" architectures')
def step_impl_project_with_chroots(context, distributions, architectures):
    """
    Create project with matrix of chroots: distributions X architectures
    """
    options = []

    def _stripped(string):
        return [x.strip() for x in string.split(",")]

    for distro in _stripped(distributions):
        if distro == "fedora-latest":
            distro = "fedora" + "-" + str(context.cli.get_latest_fedora_chroot())
        for arch in _stripped(architectures):
            chroot = distro + "-" + arch
            options.append("--chroot")
            options.append(chroot)
    name = context.scenario.name.replace(" ", "-").lower()
    name = "{}-{}".format(name, context.started)
    cmd = ["create", name] + options
    context.cli.run(cmd)
    if os.environ.get("COPR_CLEANUP", "true") != "false":
        context.add_cleanup(clean_project, context, name)
    context.last_project_name = name
