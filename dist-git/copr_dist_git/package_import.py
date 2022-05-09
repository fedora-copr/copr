# coding: utf-8

import logging
import os
import shutil
import types
import subprocess
import tempfile
import munch
import multiprocessing

# pyrpkg uses os.getlogin(). It requires tty which is unavailable when we run this script as a daemon
# very dirty solution for now
import pwd

os.getlogin = lambda: pwd.getpwuid(os.getuid())[0]
# monkey patch end

from pyrpkg import Commands
from pyrpkg.errors import rpkgError

from .exceptions import PackageImportException

from . import helpers

log = logging.getLogger(__name__)


def my_upload_fabric(opts):
    def my_upload(repo_dir, reponame, abs_filename, filehash, offline=False):
        """
        This is a replacement function for uploading sources.
        Rpkg uses upload.cgi for uploading which doesn't make sense
        on the local machine.
        """
        filename = os.path.basename(abs_filename)
        destination = os.path.join(opts.lookaside_location, reponame,
                                   filename, filehash, filename)

        if not os.path.isdir(os.path.dirname(destination)):
            try:
                os.makedirs(os.path.dirname(destination))
            except OSError as e:
                log.exception(str(e))

        if not os.path.exists(destination):
            shutil.copyfile(abs_filename, destination)

    return my_upload


def sync_branch(new_branch, branch_commits, message):
    """
    Reset the 'new_branch' contents to contents of all branches in
    already in 'branch_commits.  But if possible, try to fast-forward merge
    only to minimize the git payload and to keep the git history as flatten
    as possible across all branches. Before calling this method, ensure that
    you are in the git directory and the 'new_branch' is checked out.
    """
    for branch in branch_commits:
        # Try to fast-forward merge against any other already pushed branch.
        # Note that if the branch is already there then merge request is no-op.
        if not subprocess.call(['git', 'merge', branch, '--ff-only'], encoding='utf-8'):
            log.debug("merged '{0}' fast forward into '{1}' or noop".format(branch, new_branch))
            return

    # No --fast-forward merge possible -> reset to the first available one.
    branch = next(iter(branch_commits))
    log.debug("resetting branch '{0}' to contents of '{1}'".format(new_branch, branch))
    subprocess.check_call(['git', 'read-tree', '-m', '-u', branch], encoding='utf-8')

    # Get the AuthorDate from the original commit, to have consistent feeling.
    date = subprocess.check_output(['git', 'show', branch, '-q', '--format=%ai'], encoding='utf-8')

    if subprocess.call(['git', 'diff', '--cached', '--exit-code'], encoding='utf-8'):
        # There's something to commit.
        subprocess.check_call(['git', 'commit', '--no-verify', '-m', message,
            '--date', date], encoding='utf-8')
    else:
        log.debug("nothing to commit into branch '{0}'".format(new_branch))


def refresh_cgit_listing(reponame=None):
    """
    Refresh cgit repository list. See cgit docs for more information.
    """
    try:
        cmd = ["copr-dist-git-refresh-cgit"]
        if reponame:
            cmd += [reponame]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
    except OSError as e:
        log.error(str(e))
    except subprocess.CalledProcessError as e:
        log.error("cmd: {}, rc: {}, msg: {}".format(cmd, e.returncode, e.output.strip()))


def setup_git_repo(reponame, branches):
    """
    Invoke DistGit repo setup procedures.

    :param str reponame: name of the repository to be created
    :param str branches: branch names to be created inside that repo
    """
    log.info("make sure repos exist: {}".format(reponame))
    brand_new_package = False
    try:
        cmd = ["/usr/share/dist-git/setup_git_package", reponame]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        brand_new_package = True
    except subprocess.CalledProcessError as e:
        log.error("cmd: {}, rc: {}, msg: {}"
                  .format(cmd, e.returncode, e.output.strip()))
        if e.returncode == 128:
            log.info("Package already exists...continuing")
        else:
            raise PackageImportException(e.output)

    if brand_new_package:
        refresh_cgit_listing(reponame)

    for branch in branches:
        try:
            cmd = ["/usr/share/dist-git/mkbranch", branch, reponame]
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        except subprocess.CalledProcessError as e:
            log.error("cmd: {}, rc: {}, msg: {}"
                      .format(cmd, e.returncode, e.output.strip()))
            if e.returncode == 128:
                log.info("Branch already exists...continuing")
            else:
                raise PackageImportException(e.output)


def cleanup_repo(repo_path):
    """
    Remove all files from the given repository
    except special ones.

    :param str repo_path: path to the repository
    """
    to_remove = []
    for f in os.listdir(repo_path):
        if f not in ['.git', '.gitignore', 'sources']:
            to_remove.append(f)
    if to_remove:
        helpers.run_cmd(
            ['git', 'rm', '-r'] + to_remove)


def import_package(opts, namespace, branches, srpm_path, pkg_name):
    """
    Import package into a DistGit repo for the given branches.

    :param Munch opts: service configuration
    :param str namespace: repo name prefix
    :param list(str) branches: list of branch names to import into
    :param str srpm_path: path to the srpm file

    :return Munch: resulting import data:
        (branch_commits, reponame, pkg_name)
    """

    reponame = "{}/{}".format(namespace, pkg_name)
    setup_git_repo(reponame, branches)

    repo_dir = tempfile.mkdtemp()
    log.debug("repo_dir: {}".format(repo_dir))

    # use rpkg lib to import the source rpm
    commands = Commands(path=repo_dir,
                        lookaside="",
                        lookasidehash="md5",
                        lookaside_cgi="",
                        gitbaseurl=opts.git_base_url,
                        anongiturl="",
                        branchre="",
                        kojiprofile="",
                        build_client="")

    # rpkg gets module_name as a basename of git url
    # we use module_name as "username/projectname/package_name"
    # basename is not working here - so I'm setting it manually
    commands.repo_name = reponame

    # rpkg calls upload.cgi script on the dist git server
    # here, I just copy the source files manually with custom function
    # I also add one parameter "repo_dir" to that function with this hack
    commands.lookasidecache.upload = types.MethodType(my_upload_fabric(opts), repo_dir)

    try:
        log.debug("clone the pkg repository into repo_dir directory")
        commands.clone(reponame, target=repo_dir)
    except Exception as e:
        log.error("Failed to clone the Git repository and add files.")
        raise PackageImportException(str(e))

    oldpath = os.getcwd()
    log.debug("Switching to repo_dir: {}".format(repo_dir))
    os.chdir(repo_dir)

    log.debug("Setting up Git user name and email.")
    helpers.run_cmd(['git', 'config', 'user.name', opts.git_user_name])
    helpers.run_cmd(['git', 'config', 'user.email', opts.git_user_email])

    message = "automatic import of {}".format(pkg_name)

    branch_commits = {}
    for branch in branches:
        log.debug("checkout '{0}' branch".format(branch))

        try:
            commands.switch_branch(branch)
        except rpkgError as ex:
            log.error(str(ex))
            continue

        try:
            if not branch_commits:
                upload_files = commands.import_srpm(srpm_path)
                if upload_files:
                    commands.upload(upload_files, replace=True)
                try:
                    log.debug("commit")
                    commands.commit(message)
                except rpkgError as e:
                    # Probably nothing to be committed.
                    log.error(str(e))
            else:
                sync_branch(branch, branch_commits, message)
        except:
            log.exception("Error during source uploading, merge, or commit.")
            continue

        try:
            log.debug("push")
            commands.push()
        except rpkgError as e:
            log.exception("Exception raised during push.")
            continue

        commands.load_commit()
        branch_commits[branch] = commands.commithash

    os.chdir(oldpath)
    shutil.rmtree(repo_dir)

    return munch.Munch(
        branch_commits=branch_commits,
        reponame=reponame,
    )
