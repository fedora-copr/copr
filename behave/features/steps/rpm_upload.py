"""
Steps for the direct RPM upload feature.
"""

import configparser
import contextlib
import os
import tempfile

import requests
from behave import when, then  # pylint: disable=no-name-in-module

from copr_behave_lib import run, run_check


# pylint: disable=missing-function-docstring


def _build_local_rpm(name, arch):
    workdir = tempfile.mkdtemp(prefix="rpm-upload-test-")
    specfile = os.path.join(workdir, "{0}.spec".format(name))
    with open(specfile, "w", encoding="utf-8") as spec_fh:
        spec_fh.write(
            "Name: {name}\n"
            "Version: 1\n"
            "Release: 1\n"
            "Summary: Throwaway package for the direct RPM upload sanity test\n"
            "License: MIT\n"
            "BuildArch: {arch}\n"
            "\n"
            "%description\n"
            "Throwaway package for the direct RPM upload sanity test.\n"
            "\n"
            "%files\n".format(name=name, arch=arch)
        )

    run_check([
        "rpmbuild", "-bb", specfile,
        "--define", "_topdir {0}".format(workdir),
        "--define", "_rpmdir {0}".format(workdir),
        "--define", "_build_id_links none",
    ])

    for root, _dirs, files in os.walk(workdir):
        for filename in files:
            if filename.endswith(".rpm"):
                return os.path.join(root, filename)
    raise RuntimeError("rpmbuild did not produce an RPM in {0}".format(workdir))


def _post_rpm_upload(context, rpm_paths):
    parser = configparser.ConfigParser()
    parser.read(context.copr_cli_config)
    login = parser["copr-cli"]["login"]
    token = parser["copr-cli"]["token"]

    owner = context.cli.whoami()
    project = context.last_project_name

    with contextlib.ExitStack() as stack:
        # multiple ("pkgs", ...) tuples under one key -- this is how
        # `requests` sends multiple files for the same multipart field name,
        # matching the "pkgs" MultipleFileField on the frontend
        files = [
            ("pkgs", (os.path.basename(path),
                      stack.enter_context(open(path, "rb")),
                      "application/x-rpm"))
            for path in rpm_paths
        ]
        return requests.post(
            "{0}/api_3/build/create/rpm-upload".format(context.frontend_url),
            auth=(login, token),
            data={
                "ownername": owner,
                "projectname": project,
                "chroot": context.system_chroot,
            },
            files=files,
            timeout=120,
        )


@when('a locally built "{name}" RPM is uploaded directly to the project')
def step_upload_rpm_directly(context, name):
    arch = context.system_chroot.rsplit("-", 1)[-1]
    rpm_path = _build_local_rpm(name, arch)
    response = _post_rpm_upload(context, [rpm_path])
    assert response.status_code == 200, \
        "upload failed ({0}): {1}".format(response.status_code, response.text)

    build_id = response.json()["id"]
    context.builds.append(build_id)
    # No custom timeout needed here: wait_success_build() polls via
    # `copr-cli watch-build`, which has no hardcoded short timeout and is
    # already used (and proven sufficient) for every other build scenario
    # that goes through a real builder VM.
    context.cli.wait_success_build(build_id)


@when('locally built "{names}" RPMs are uploaded directly to the project '
      'in one request')
def step_upload_rpms_directly(context, names):
    arch = context.system_chroot.rsplit("-", 1)[-1]
    name_list = [name.strip() for name in names.split(",")]
    rpm_paths = [_build_local_rpm(name, arch) for name in name_list]
    context.rpm_upload_response = _post_rpm_upload(context, rpm_paths)


@then('the uploaded RPM "{package_name}" is present in the repository')
def step_check_uploaded_rpm_in_repo(context, package_name):
    owner = context.cli.whoami()
    project = context.last_project_name
    project_id = context.cli.dnf_copr_project(owner, project)
    try:
        run_check(['sudo', 'dnf', '-y', 'copr', 'enable', project_id])
        (out, _) = run_check([
            "sudo", "dnf", "repoquery", "--disablerepo=*",
            "--enablerepo=*{}*".format(project), "--available",
            "--qf", "%{NAME}\n", "--noplugins",
        ])
        packages_found = set(out.strip().splitlines())
        assert package_name in packages_found, (
            "Expected '{}' in repoquery output, got: {}".format(
                package_name, packages_found))

        run_check([
            "sudo", "dnf", "-y", "install", "--disablerepo=*",
            "--enablerepo=*{}*".format(project), package_name,
        ])
        (rpm_out, _) = run_check(["rpm", "-q", package_name])
        assert package_name in rpm_out, (
            "Expected '{}' to be installed, got: {}".format(
                package_name, rpm_out))
    finally:
        run(['sudo', 'dnf', '-y', 'remove', package_name])
        run(['sudo', 'dnf', 'copr', 'remove', project_id])


@then('the upload request is rejected with status code {status_code:d}')
def step_check_upload_rejected(context, status_code):
    response = context.rpm_upload_response
    assert response.status_code == status_code, (
        "Expected status code {0}, got {1}: {2}".format(
            status_code, response.status_code, response.text))
