# coding: utf-8

from multiprocessing import Process, Manager
import logging
import os
import shutil
import traceback
import types
import grp
import subprocess

# pyrpkg uses os.getlogin(). It requires tty which is unavailable when we run this script as a daemon
# very dirty solution for now
import pwd

os.getlogin = lambda: pwd.getpwuid(os.getuid())[0]
# monkey patch end

from pyrpkg import Commands
from pyrpkg.errors import rpkgError

log = logging.getLogger(__name__)

def my_upload_fabric(opts):
    def my_upload(repo_dir, reponame, abs_filename, filehash):
        """
        This is a replacement function for uploading sources.
        Rpkg uses upload.cgi for uploading which doesn't make sense
        on the local machine.
        """
        filename = os.path.basename(abs_filename)
        destination = os.path.join(opts.lookaside_location, reponame,
                                   filename, filehash, filename)

        # hack to allow "uploading" into lookaside
        current_gid = os.getgid()
        apache_gid = grp.getgrnam("apache").gr_gid
        os.setgid(apache_gid)

        if not os.path.isdir(os.path.dirname(destination)):
            try:
                os.makedirs(os.path.dirname(destination))
            except OSError as e:
                log.exception(str(e))

        if not os.path.exists(destination):
            shutil.copyfile(abs_filename, destination)

        os.setgid(current_gid)

    return my_upload


def actual_do_git_srpm_import(opts, src_filepath, task, tmp_dir, result):
    """
    Function to be invoked through multiprocessing
    :param opts: Bunch object with config
    :param src_filepath:
    :param ImportTask task:
    :param tmp_dir:

    :param result: shared dict from Manager().dict()
    """

    repo_dir = os.path.join(tmp_dir, task.package_name)
    log.debug("repo_dir: {}".format(repo_dir))
    # use rpkg for importing the source rpm
    commands = Commands(path=repo_dir,
                        lookaside="",
                        lookasidehash="md5",
                        lookaside_cgi="",
                        gitbaseurl=opts.git_base_url,
                        anongiturl="",
                        branchre="",
                        kojiconfig="",
                        build_client="")
    # rpkg gets module_name as a basename of git url
    # we use module_name as "username/projectname/package_name"
    # basename is not working here - so I'm setting it manually
    module = "{}/{}/{}".format(task.user, task.project, task.package_name)
    commands.module_name = module
    # rpkg calls upload.cgi script on the dist git server
    # here, I just copy the source files manually with custom function
    # I also add one parameter "repo_dir" to that function with this hack
    commands.lookasidecache.upload = types.MethodType(my_upload_fabric(opts), repo_dir)
    try:
        log.info("clone the '{0}' pkg repository into tmp directory".format(module))
        commands.clone(module, tmp_dir)
    except:
        log.exception("Failed to clone the repo.")
        return

    message = "import_srpm"
    committed = set()
    for branch in task.branches:
        result[branch] = False # failure by default
        log.info("checkout '{0}' branch".format(branch))
        commands.switch_branch(branch)

        oldpath = os.getcwd()
        try:
            os.chdir(repo_dir) # we need to be in repo_dir for the following to work
            if not committed:
                log.info("save the files from {0} into lookaside cache".format(src_filepath))
                upload_files = commands.import_srpm(src_filepath)
                commands.upload(upload_files, replace=True)
                try:
                    commands.commit(message)
                except Exception:
                    log.exception("error during commit (probably nothing to commit), ignored")
            else:
                sync_actual_branch(committed, branch, message)

            # Mark the branch as committed.
            committed.add(branch)
        except:
            log.exception("Error during upload, commit or merge.")
            continue
        finally:
            os.chdir(oldpath)

        log.debug("git push")
        message = "import_srpm"
        try:
            commands.push()
            log.debug("commit and push done")
        except rpkgError:
            log.exception("error during push, ignored")

        try:
            # Ensure that nothing was lost.
            commands.check_repo(all_pushed=True)
            # 'commands.commithash' is "cached" property, we need to re-fresh
            # the actual commit id..
            commands.load_commit()
            result[branch] = commands.commithash
        except:
            pass


def sync_actual_branch(committed_branches, actual_branch, message):
    """
    Reset the 'actual_branch' contents to contents of all branches in
    already 'committed_branches' (param is set of strings).  But if possible,
    try to fast-forward merge only to minimize the git payload and to keep the
    git history as flatten as possible across all branches.
    Before calling this method, ensure that you are in the git directory and the
    'actual_branch' is checked out.
    """
    for branch in committed_branches:
        # Try to fast-forward merge against any other already pushed branch.
        # Note that if the branch is already there then merge request is no-op.
        if not subprocess.call(['git', 'merge', branch, '--ff-only']):
            log.debug("merged '{0}' fast forward into '{1}' or noop".format(branch, actual_branch))
            return

    # No --fast-forward merge possible -> reset to the first available one.
    branch = next(iter(committed_branches))
    log.debug("resetting branch '{0}' to contents of '{1}'".format(actual_branch, branch))
    subprocess.check_call(['git', 'read-tree', '-m', '-u', branch])

    # Get the AuthorDate from the original commit, to have consistent feeling.
    date = subprocess.check_output(['git', 'show', branch, '-q', '--format=%ai'])

    if subprocess.call(['git', 'diff', '--cached', '--exit-code']):
        # There's something to commit.
        subprocess.check_call(['git', 'commit', '--no-verify', '-m', message,
            '--date', date])
    else:
        log.debug("nothing to commit into branch '{0}'".format(actual_branch))


def do_git_srpm_import(opts, src_filepath, task, tmp_dir):
    # should be run in the forked process, see:
    # - https://bugzilla.redhat.com/show_bug.cgi?id=1253335
    # - https://github.com/gitpython-developers/GitPython/issues/304

    result_dict = Manager().dict()
    proc = Process(target=actual_do_git_srpm_import,
                   args=(opts, src_filepath, task, tmp_dir, result_dict))
    proc.start()
    proc.join()
    return result_dict

def do_distgit_import(opts, tarball_path, spec_path, task, tmp_dir):
    repo_dir = os.path.join(tmp_dir, task.package_name)
    log.debug("repo_dir: {}".format(repo_dir))

    # use rpkg for importing the source rpm
    commands = Commands(path=repo_dir,
                        lookaside="",
                        lookasidehash="md5",
                        lookaside_cgi="",
                        gitbaseurl=opts.git_base_url,
                        anongiturl="",
                        branchre="",
                        kojiconfig="",
                        build_client="")

    # rpkg gets module_name as a basename of git url
    # we use module_name as "username/projectname/package_name"
    # basename is not working here - so I'm setting it manually
    module = "{}/{}/{}".format(task.user, task.project, task.package_name)
    commands.module_name = module

    # rpkg calls upload.cgi script on the dist git server
    # here, I just copy the source files manually with custom function
    # I also add one parameter "repo_dir" to that function with this hack
    commands.lookasidecache.upload = types.MethodType(my_upload_fabric(opts), repo_dir)

    result = {}

    try:
        log.info("clone the pkg repository into tmp directory")
        commands.clone(module, tmp_dir)
    except:
        log.exception("Failed to clone the Git repository and add files.")
        return result

    message = "import_mock_scm"
    committed = set()
    for branch in task.branches:
        result[branch] = False # failure by default
        log.info("checkout '{0}' branch".format(branch))
        commands.switch_branch(branch)

        if not committed:
            shutil.copy(spec_path, repo_dir)
            for f in ('.gitignore', 'sources'):
                if not os.path.exists(repo_dir+"/"+f):
                    open(repo_dir+"/"+f, 'w').close()
            commands.repo.index.add(('.gitignore', 'sources', os.path.basename(spec_path)))

        oldpath = os.getcwd()
        try:
            os.chdir(repo_dir) # we need to be in repo_dir for the following to work
            log.info("Working in: {0}".format(repo_dir))

            if not committed:
                if tarball_path:
                    log.info("save the source files into lookaside cache")
                    commands.upload([tarball_path], replace=True)
                try:
                    commands.commit(message)
                except Exception:
                    # Probably nothing to be committed.  We historically ignore isues here.
                    log.exception("error during commit (probably nothing to commit), ignored")
            else:
                sync_actual_branch(committed, branch, message)

            # Mark the branch as committed.
            committed.add(branch)

        except:
            log.exception("Error during source uploading, merge, or commit")
            continue
        finally:
            os.chdir(oldpath)


        log.debug("git push")
        try:
            commands.push()
            log.debug("commit and push done")
        except rpkgError:
            log.exception("error during push, ignored")

        commands.load_commit()
        result[branch] = commands.commithash

    return result
