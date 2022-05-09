# coding: utf-8

import tempfile
import pytest
import shutil
import time
import os
import logging

from unittest import mock

from munch import Munch
from subprocess import check_output

from copr_dist_git.package_import import import_package

def scriptdir():
    return os.path.dirname(os.path.realpath(__file__))

@pytest.yield_fixture
def mc_setup_git_repo():
    with mock.patch("{}.setup_git_repo".format('copr_dist_git.package_import')) as handle:
        yield handle


@pytest.yield_fixture
def mc_group():
    with mock.patch("os.setgid") as handle:
        yield handle


@pytest.yield_fixture
def mc_chroot():
    with mock.patch("os.chroot") as handle:
        yield handle


@pytest.yield_fixture(scope='module')
def tmpdir():
    origdir = os.getcwd()
    tdir = tempfile.mkdtemp()
    print("working in " + tdir)
    os.chdir(tdir)
    yield tdir
    os.chdir(origdir)
    shutil.rmtree(tdir, ignore_errors=True)


@pytest.yield_fixture
def git_repos(tmpdir):
    dirname = 'git_repos'
    os.mkdir(dirname)
    yield os.path.join(tmpdir, dirname)
    shutil.rmtree('git_repos', ignore_errors=True)


@pytest.yield_fixture
def origin(git_repos):
    print("creating origin")
    modulename = 'bob/blah/quick-package'
    abspath = os.path.join(git_repos, modulename)
    assert 0 == os.system(
    """ set -e
    rm -rf work
    mkdir -p {module}
    git init --bare {module}
    git clone {module} work
    cd work
    echo 'empty git repo' > README
    git add README
    git config user.email "you@example.com"
    git config user.name "Your Name"
    git commit -m 'initial commit'
    git push
    """.format(module=abspath)
    )
    yield os.path.join(git_repos, modulename)
    shutil.rmtree('work', ignore_errors=True)


@pytest.yield_fixture
def branches(origin):
    branches = ['f20', 'epel7', 'el6', 'fedora/26', 'rhel-7']
    middle_branches = ['el6', 'fedora/26']
    border_branches = ['f20', 'epel7', 'rhel-7']

    assert 0 == os.system(
    """ set -e
    cd work
    for branch in {branches}
    do
        git branch $branch
        git checkout $branch
        git push origin $branch
    done
    """.format(branches=' '.join(branches))
    )

    yield (origin, branches, middle_branches, border_branches)


@pytest.yield_fixture
def lookaside(tmpdir):
    assert 0 == os.system(
    """ set -e
    mkdir -p lookaside
    """)
    yield 'lookaside'
    shutil.rmtree('lookaside', ignore_errors=True)


@pytest.yield_fixture
def opts_basic(tmpdir, lookaside):
    class _:
        pass
    opts = _()
    opts.lookaside_location = os.path.join(tmpdir, 'lookaside')
    opts.git_base_url = os.path.join(tmpdir, 'git_repos/%(module)s')
    opts.cgit_pkg_list_location = os.path.join(tmpdir, 'git_repos/cgit_list')
    opts.git_user_name = os.path.join(tmpdir, 'git_user_name')
    opts.git_user_email = os.path.join(tmpdir, 'git_user_email')
    yield opts

srpm_cache = {}

def get_srpm(version):
    if version in srpm_cache:
        return srpm_cache[version]

    assert 0 == os.system("""set -e
    mkdir -p srpm_dir && cd srpm_dir
    export dummy_version={version}
    {script_dir}/generate_qiuck_package
    """.format(script_dir=scriptdir(), version=version))

    srpm_path = os.path.join(os.getcwd(), 'srpm_dir',
                             'quick-package-{0}-0.src.rpm'.format(version))
    result = (
        srpm_path,
        Munch({
            'package_name': 'quick-package',
            'user': 'bob',
            'project':'blah',
        })
    )

    srpm_cache[version] = result
    return result


def branch_hash(directory, branch):
    cmd = 'set -e && cd {0} && git rev-parse {1}'.format(directory, branch)
    return check_output(cmd, shell=True, encoding='utf-8')


def compare_branches(branches, remote, local=None, result_hash=None):
    sample_hash = branch_hash(remote, branches[0])

    for branch in branches[1:]:
        remote_hash = branch_hash(remote, branch)
        assert remote_hash
        assert remote_hash == sample_hash

        if local:
            branch_hash(local, branch) == sample_hash
        if result_hash:
            assert result_hash[branch] in sample_hash

    return sample_hash


@pytest.fixture
def initial_commit_everywhere(request, branches, mc_group, mc_chroot, opts_basic, mc_setup_git_repo):
    origin, all_branches, _, _ = branches

    # Commit first version and compare remote side with local side.
    result = request.instance.commit_to_branches(all_branches, opts_basic, 1)
    init_hash = compare_branches(all_branches, origin, result_hash=result)

    return (branches, opts_basic, init_hash)


class TestMerging(object):

    def commit_to_branches(self, to_branches, opts, version):
        srpm_path, package_desc = get_srpm(version)
        name = package_desc['package_name']
        import_result = import_package(opts, 'bob/blah', to_branches, srpm_path, name)
        return import_result['branch_commits']

    def setup_method(self, method):
        srpm_cache = {}

    def test_merged_everything(self, initial_commit_everywhere, mc_setup_git_repo):
        branches, opts, v1_hash = initial_commit_everywhere
        origin, all_branches, middle_branches, border_branches = branches

        result = self.commit_to_branches(border_branches, opts, 2)
        v2_hash = compare_branches(border_branches, origin, result_hash=result)
        unchanged = compare_branches(middle_branches, origin)
        assert unchanged == v1_hash
        assert v2_hash != v1_hash

        # And commit again to all branches.  Because we first committed to
        # border branches, the "merge" algorithm is able to "fast forward" merge
        # also middle brancehs.... So all branches should have the same hash
        # now.
        result = self.commit_to_branches(all_branches, opts, 3)
        v3_hash = compare_branches(all_branches, origin, result_hash=result)
        assert v3_hash != v1_hash
        assert v3_hash != v2_hash

    def test_diverge_middle_branches(self, initial_commit_everywhere, mc_setup_git_repo):
        branches, opts, v1_hash = initial_commit_everywhere
        origin, all_branches, middle_branches, border_branches = branches

        result = self.commit_to_branches(middle_branches, opts, 2)
        v2_hash = compare_branches(middle_branches, origin, result_hash=result)
        unchanged = compare_branches(border_branches, origin)
        assert unchanged == v1_hash
        assert v2_hash != v1_hash

        # This means that (a) first we commit second patch to 'border_branches',
        # and thatn we commit third patch to 'middle_branches'.
        result = self.commit_to_branches(all_branches, opts, 3)
        v3_hash_a = compare_branches(middle_branches, origin, result_hash=result)
        v3_hash_b = compare_branches(border_branches, origin, result_hash=result)

        assert v3_hash_a != v3_hash_b
        assert v3_hash_a != v2_hash
        assert v3_hash_b != v2_hash
        assert v3_hash_a != v1_hash
        assert v3_hash_b != v1_hash

    def test_no_op_1(self, initial_commit_everywhere, mc_setup_git_repo):
        branches, opts, v1_hash = initial_commit_everywhere
        origin, all_branches, middle_branches, border_branches = branches

        # This imports the same srpm, which means nothing should change in the
        # git repository.
        result = self.commit_to_branches(all_branches, opts, 1)
        unchanged = compare_branches(all_branches, origin, result_hash=result)
        # Hash is unchanged, while still the 'result' above is fine!
        assert unchanged == v1_hash

        result = self.commit_to_branches(border_branches, opts, 2)
        v2_hash_a = compare_branches(border_branches, origin, result_hash=result)
        assert v2_hash_a != v1_hash

        # This should sync the remaining branches.  It also means that
        # border_branches are importing the same version, thus nothing happens
        # to them.
        result = self.commit_to_branches(all_branches, opts, 2)
        v2_hash_b = compare_branches(all_branches, origin, result_hash=result)
        assert v2_hash_a == v2_hash_b

        result = self.commit_to_branches(middle_branches, opts, 3)
        v3_hash_a = compare_branches(middle_branches, origin, result_hash=result)
        assert v3_hash_a != v2_hash_a

        # Get different timestamp to get different hash.
        time.sleep(1)

        result = self.commit_to_branches(all_branches, opts, 3)
        v3_hash_b = compare_branches(border_branches, origin, result_hash=result)
        assert v3_hash_a != v3_hash_b
        assert v3_hash_a != v2_hash_a
