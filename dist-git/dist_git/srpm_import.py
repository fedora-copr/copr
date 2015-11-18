# coding: utf-8


import os
import types
import shutil
import logging
from multiprocessing import Process, Manager

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
    def my_upload(repo_dir, reponame, filename, filehash):
        """
        This is a replacement function for uploading sources.
        Rpkg uses upload.cgi for uploading which doesn't make sense
        on the local machine.
        """
        source = os.path.join(repo_dir, filename)
        destination = os.path.join(opts.lookaside_location, reponame,
                                   filename, filehash, filename)
        if not os.path.exists(destination):
            os.makedirs(os.path.dirname(destination))
            shutil.copyfile(source, destination)
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

    # I need to use git via SSH because of gitolite as it manages
    # permissions with it's hook that relies on gitolite console
    # which is a default shell on SSH

    git_base_url = "ssh://copr-dist-git@localhost/%(module)s"
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
    log.debug("clone the pkg repository into tmp directory")
    commands.clone(module, tmp_dir, task.branch)
    log.debug("import the source rpm into git and save filenames of sources")
    try:
        upload_files = commands.import_srpm(src_filepath)
    except Exception:
        log.exception("Failed to import the source rpm: {}".format(src_filepath))
        return
        # raise PackageImportException()
    log.info("save the source files into lookaside cache")
    commands.upload(upload_files, replace=True)
    log.debug("git push")
    #message = "Import of {} {}".format(task.package_name, task.package_version)
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
