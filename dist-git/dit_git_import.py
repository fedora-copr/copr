import os
import types
import shutil
import tempfile
from pyrpkg import Commands
from pyrpkg.errors import rpkgError

# Example usage:
#
# user = "asamalik"
# project = "project-for-dist-git"
# pkg_name = "devtoolset-3"
# branch = "f20"
# filepath = "/tmp/rh-php56-php-5.6.5-5.el7.src.rpm"
#
# git_hash = import_srpm(user, project, pkg_name, branch, filepath)


def _my_upload(repo_dir, reponame, filename, filehash):
    """
    This is a replacement function for uploading sources.
    Rpkg uses upload.cgi for uploading which doesn't make sense
    on the local machine.
    """
    lookaside = "/var/lib/dist-git/cache/lookaside/pkgs/"
    source = os.path.join(repo_dir, filename)
    destination = os.path.join(lookaside, reponame, filename, filehash, filename)
    if not os.path.exists(destination):
        os.makedirs(os.path.dirname(destination))
        shutil.copyfile(source, destination)

def import_srpm(user, project, pkg, branch, filepath):
    """
    Imports a source rpm file into local dist git.
    Repository name is in the Copr Style: user/project/package
    filepath is a srpm file locally downloaded somewhere
    """
    # I need to use git via SSH because of gitolite as it manages
    # permissions with it's hook that relies on gitolite console
    # which is a default shell on SSH
    gitbaseurl = "ssh://frank@localhost/%(module)s"
    tmp = tempfile.mkdtemp()
    try:
        repo_dir = os.path.join(tmp, pkg)

        # use rpkg for importing the source rpm
        commands = Commands(path          =repo_dir,
                            lookaside     ="",
                            lookasidehash ="md5",
                            lookaside_cgi ="",
                            gitbaseurl    =gitbaseurl,
                            anongiturl    ="",
                            branchre      ="",
                            kojiconfig    ="",
                            build_client  ="")

        # rpkg gets module_name as a basename of git url
        # we use module_name as "username/projectname/packagename"
        # basename is not working here - so I'm setting it manually
        module = "{}/{}/{}".format(user, project, pkg)
        commands.module_name = module
        # rpkg calls upload.cgi script on the dist git server
        # here, I just copy the source files manually with custom function
        # I also add one parameter "repo_dir" to that function with this hack
        commands.lookasidecache.upload = types.MethodType(_my_upload, repo_dir)

        # clone the pkg repository into tmp directory
        #module = "{}/{}/{}.git".format(user, project, pkg)
        #giturl = gitbaseurl % {'module': module}
        #cmd = ['git', 'clone', "-b", "f20",  giturl]
        #call(cmd, cwd=tmp)
        commands.clone(module, tmp, branch)

        # import the source rpm into git and save filenames of sources
        uploadfiles = commands.import_srpm(filepath)

        # save the source files into lookaside cache
        commands.upload(uploadfiles, replace=True)

        # git push
        message = "Import of {}".format(os.path.basename(filepath))
        #call(["git", "commit", "-m", message], cwd=repo_dir)
        #call(["git", "push"], cwd=repo_dir)
        try:
            commands.commit(message)
            commands.push()
        except rpkgError:
            pass
    finally:
        shutil.rmtree(tmp)
    return commands.commithash
