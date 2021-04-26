"""
Fixtures for Copr Backend
"""

import os
from pytest import fixture
import shutil
import tarfile
import tempfile
import subprocess
from unittest import mock

from copr_backend.helpers import call_copr_repo

# We intentionally let fixtures depend on other fixtures.
# pylint: disable=redefined-outer-name

class CoprTestFixtureContext():
    pass

@fixture
def f_temp_directory():
    "create and return temporary directory"
    directory = tempfile.mkdtemp(prefix="copr-backend-test-")
    ctx = CoprTestFixtureContext()
    ctx.workdir = directory
    yield ctx
    shutil.rmtree(directory)

@fixture
def f_testresults(f_temp_directory):
    "extract testresults.tar.gz into temporary directory"
    ctx = f_temp_directory
    src_path = os.path.join(os.path.dirname(__file__),
                            "_resources", "testresults.tar.gz")

    with tarfile.open(src_path, "r:gz") as tfile:
        tfile.extractall(ctx.workdir)
    ctx.testresults = os.path.join(ctx.workdir, 'testresults')
    yield ctx

@fixture
def f_empty_repos(f_testresults):
    """
    create empty john/empty/<chroots> directories, and run
    createrepo_c there
    """
    ctx = f_testresults
    ctx.empty_dir = os.path.join(ctx.workdir, 'john', 'empty')
    ctx.chroots = ['fedora-rawhide-x86_64', 'epel-7-x86_64']
    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot)
        os.makedirs(chdir)
        with mock.patch.dict(os.environ, {'COPR_TESTSUITE_NO_OUTPUT': '1'}):
            assert call_copr_repo(chdir)
    yield ctx

@fixture
def f_first_build(f_empty_repos):
    """
    Simulate that first build finished, but no craterepo was run, yet.
    """
    ctx = f_empty_repos

    source = os.path.join(
        ctx.testresults,
        '@copr', 'prunerepo', 'fedora-23-x86_64', '00000041-prunerepo',
        'prunerepo-1.1-1.fc23.noarch.rpm',
    )

    build = '00000001-prunerepo'
    ctx.builds = [build]
    ctx.first_build = build

    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot, build)
        os.makedirs(chdir)
        shutil.copy(source, chdir)

    yield ctx

@fixture
def f_acr_on_and_first_build(f_first_build):
    """
    Simulate that we have ACR=1 and that first build finished, while
    no createrepo run after the build, yet.
    """
    ctx = f_first_build
    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot, 'devel')
        os.mkdir(chdir)
        subprocess.check_output(['createrepo_c', chdir])
    yield ctx

@fixture
def f_second_build(f_first_build):
    """
    Simulate that second build finished right after the first one,
    and no create repo was run yet.
    """
    ctx = f_first_build
    source = os.path.join(ctx.workdir, '@copr', 'prunerepo', 'fedora-23-x86_64',
                          '00000049-example', 'example-1.0.4-1.fc23.x86_64.rpm')
    source = os.path.join(ctx.testresults, '@copr', 'prunerepo',
                          'fedora-23-x86_64', '00000049-example',
                          'example-1.0.4-1.fc23.x86_64.rpm')
    ctx.build = '00000002-example'
    ctx.builds.append(ctx.build)
    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot, ctx.build)
        os.mkdir(chdir)
        shutil.copy(source, chdir)

    yield ctx

@fixture
def f_third_build(f_second_build):
    """
    Same as ``f_second_build``, but one more build.
    """
    ctx = f_second_build
    source = os.path.join(os.environ["TEST_DATA_DIRECTORY"],
                          "build_results", "00848963-example",
                          "example-1.0.14-1.fc30.x86_64.rpm")
    build = '00000003-example'
    ctx.builds.append(build)
    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot, build)
        os.mkdir(chdir)
        shutil.copy(source, chdir)
    yield ctx


@fixture
def f_builds_to_prune(f_empty_repos):
    """
    Prepare repositories to test prunerepo.
    """
    ctx = f_empty_repos
    source = os.path.join(os.environ["TEST_DATA_DIRECTORY"],
                          "to_prune")
    for chroot in ctx.chroots:
        chdir = os.path.join(ctx.empty_dir, chroot)
        shutil.rmtree(chdir)
        shutil.copytree(source, chdir)
    yield ctx
