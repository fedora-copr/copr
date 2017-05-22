# coding: utf-8

from multiprocessing import Process, Manager
import logging
import os
import shutil
import traceback
import types
import grp

# pyrpkg uses os.getlogin(). It requires tty which is unavailable when we run this script as a daemon
# very dirty solution for now
import pwd
from dist_git.exceptions import PackageImportException

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

    git_base_url = "/var/lib/dist-git/git/%(module)s"
    repo_dir = os.path.join(tmp_dir, task.package_name)
    log.debug("repo_dir: {}".format(repo_dir))
    # use rpkg for importing the source rpm
    commands = Commands(path=repo_dir,
                        lookaside="",
                        lookasidehash="md5",
                        lookaside_cgi="",
                        gitbaseurl=git_base_url,
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
        log.info("clone the pkg repository into tmp directory")
        commands.clone(module, tmp_dir, task.branch)
        log.info("import the source rpm into git and save filenames of sources")
        upload_files = commands.import_srpm(src_filepath)
    except:
        log.exception("Failed to import the source rpm: {}".format(src_filepath))
        return

    log.info("save the source files into lookaside cache")
    oldpath = os.getcwd()
    os.chdir(repo_dir) # we need to be in repo_dir for the following to work
    try:
        commands.upload(upload_files, replace=True)
    except:
        log.exception("Error during source uploading")
        return

    os.chdir(oldpath)

    log.debug("git push")
    message = "import_srpm"
    try:
        commands.commit(message)
        commands.push()
        log.debug("commit and push done")
    except rpkgError:
        log.exception("error during commit and push, ignored")

    result["hash"] = commands.commithash


def do_git_srpm_import(opts, src_filepath, task, tmp_dir):
    # should be run in the forked process, see:
    # - https://bugzilla.redhat.com/show_bug.cgi?id=1253335
    # - https://github.com/gitpython-developers/GitPython/issues/304

    result_dict = Manager().dict()
    proc = Process(target=actual_do_git_srpm_import,
                   args=(opts, src_filepath, task, tmp_dir, result_dict))
    proc.start()
    proc.join()
    if result_dict.get("hash") is None:
        raise PackageImportException("Failed to import the source rpm: {}".format(src_filepath))

    return str(result_dict["hash"])

def do_distgit_import(opts, tarball_path, spec_path, task, tmp_dir):
    git_base_url = "/var/lib/dist-git/git/%(module)s"

    repo_dir = os.path.join(tmp_dir, task.package_name)
    log.debug("repo_dir: {}".format(repo_dir))

    # use rpkg for importing the source rpm
    commands = Commands(path=repo_dir,
                        lookaside="",
                        lookasidehash="md5",
                        lookaside_cgi="",
                        gitbaseurl=git_base_url,
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
        log.info("clone the pkg repository into tmp directory")
        commands.clone(module, tmp_dir, task.branch)

        shutil.copy(spec_path, repo_dir)

        for f in ('.gitignore', 'sources'):
            if not os.path.exists(repo_dir+"/"+f):
                open(repo_dir+"/"+f, 'w').close()

        commands.repo.index.add(('.gitignore', 'sources', os.path.basename(spec_path)))
    except:
        log.exception("Failed to clone the Git repository and add files.")
        return

    oldpath = os.getcwd()
    log.info(repo_dir)

    os.chdir(repo_dir) # we need to be in repo_dir for the following to work
    try:
        log.info("save the source files into lookaside cache")
        commands.upload([tarball_path], replace=True)
    except:
        log.exception("Error during source uploading")
        return

    os.chdir(oldpath)

    log.debug("git push")
    message = "import_srpm"
    try:
        commands.commit(message)
        commands.push()
        log.debug("commit and push done")
    except rpkgError:
        log.exception("error during commit and push, ignored")

    return commands.commithash
