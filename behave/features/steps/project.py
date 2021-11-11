"""
Steps that create Copr projects
"""

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
