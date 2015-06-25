import os
import json
import time
import types
import urllib
import shutil
import tempfile
from requests import get
from requests import post
from pyrpkg import Commands
from subprocess import call
from pyrpkg.errors import rpkgError

from helpers import DistGitConfigReader

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
    gitbaseurl = "ssh://copr-dist-git@localhost/%(module)s"
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
        git_hash = commands.commithash
    finally:
        shutil.rmtree(tmp)
    return git_hash


class DistGitImporter():
    def __init__(self):
        self.config_reader = DistGitConfigReader()
        self.opts = self.config_reader.read()

    def run(self):
        get_url = "{}/backend/uploading/".format(self.opts.frontend_base_url)
        upload_url = "{}/backend/upload-completed/".format(self.opts.frontend_base_url)
        auth = ("user",self.opts.frontend_auth)
        headers = {"content-type": "application/json"}

        tmp = tempfile.mkdtemp()
        try:
            while(True):
                # get the data
                r = get(get_url)
                try:
                    task = r.json()["builds"][0]

                    task_id = task["task_id"]
                    user = task["user"]
                    project = task["project"]
                    package = task["package"]
                    branch = task["branch"]
                    package_url = task["package_url"]
                except:
                    time.sleep(10)
                    continue

                # make sure repos exist
                reponame = "{}/{}/{}".format(user, project, package)
                call(["/usr/share/dist-git/git_package.sh", reponame])
                call(["/usr/share/dist-git/git_branch.sh", branch, reponame])
                
                # download the package
                filepath = os.path.join(tmp, os.path.basename(package_url))
                urllib.urlretrieve(package_url, filepath)

                # import it and delete the srpm
                git_hash = import_srpm(user, project, package, branch, filepath)
                os.remove(filepath)

                # send a response
                data = {"task_id": task_id,
                        "repo_name": reponame,
                        "git_hash": git_hash}
                post(upload_url, auth=auth, data=json.dumps(data), headers=headers)
        finally:
            shutil.rmtree(tmp)

def main():
    importer = DistGitImporter()
    try:
        importer.run()
    except KeyboardInterrupt:
        return

if __name__ == "__main__":
    main()

