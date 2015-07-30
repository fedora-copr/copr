#!/usr/bin/python

import os
import json
import time
import types
import urllib
import shutil
import tempfile
import logging
import subprocess

from requests import get
from requests import post

# pyrpkg uses os.getlogin(). It requires tty which is unavailable when we run this script as a daemon
# very dirty solution for now
import pwd
import sys

os.getlogin = lambda: pwd.getpwuid(os.getuid())[0]
# monkey patch end

from pyrpkg import Commands
from subprocess import call
from pyrpkg.errors import rpkgError

from helpers import DistGitConfigReader

log = logging.getLogger(__name__)


# Example usage:
#
# user = "asamalik"
# project = "project-for-dist-git"
# pkg_name = "devtoolset-3"
# branch = "f20"
# filepath = "/tmp/rh-php56-php-5.6.5-5.el7.src.rpm"
#
# git_hash = import_srpm(user, project, pkg_name, branch, filepath)


class PackageImportException(Exception):
    pass


class PackageDownloadException(Exception):
    pass


class PackageQueryException(Exception):
    pass


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
        log.debug("repo_dir: {}".format(repo_dir))
        # use rpkg for importing the source rpm
        commands = Commands(path=repo_dir,
                            lookaside="",
                            lookasidehash="md5",
                            lookaside_cgi="",
                            gitbaseurl=gitbaseurl,
                            anongiturl="",
                            branchre="",
                            kojiconfig="",
                            build_client="")

        # rpkg gets module_name as a basename of git url
        # we use module_name as "username/projectname/packagename"
        # basename is not working here - so I'm setting it manually
        module = "{}/{}/{}".format(user, project, pkg)
        commands.module_name = module
        # rpkg calls upload.cgi script on the dist git server
        # here, I just copy the source files manually with custom function
        # I also add one parameter "repo_dir" to that function with this hack
        commands.lookasidecache.upload = types.MethodType(_my_upload, repo_dir)

        log.debug("clone the pkg repository into tmp directory")
        commands.clone(module, tmp, branch)

        log.debug("import the source rpm into git and save filenames of sources")
        try:
            uploadfiles = commands.import_srpm(filepath)
        except Exception:
            log.exception("Failed to import the source rpm: {}".format(filepath))
            raise PackageImportException

        log.info("save the source files into lookaside cache")
        commands.upload(uploadfiles, replace=True)

        log.debug("git push")
        message = "Import of {}".format(os.path.basename(filepath))
        try:
            commands.commit(message)
            commands.push()
            log.debug("commit and push done")
        except rpkgError:
            pass
        git_hash = commands.commithash
    finally:
        shutil.rmtree(tmp)
    return git_hash


def pkg_name_evr(pkg):
    """
    Queries a package for its name and evr (epoch:version-release)
    """
    log.debug("Verifying packagage, getting  name and version.")
    cmd = ['rpm', '-qp', '--nosignature', '--qf', '%{NAME} %{EPOCH} %{VERSION} %{RELEASE}', pkg]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        output, error = proc.communicate()
    except OSError as e:
        raise PackageQueryException(e)
    if error:
        raise PackageQueryException('Error querying srpm: %s' % error)

    try:
        name, epoch, version, release = output.split(" ")
    except ValueError as e:
        raise PackageQueryException(e)

    # Epoch is an integer or '(none)' if not set
    if epoch.isdigit():
        evr = "{}:{}-{}".format(epoch, version, release)
    else:
        evr = "{}-{}".format(version, release)

    return name, evr


class DistGitImporter():
    def __init__(self, opts):
        self.opts = opts

        self.get_url = "{}/backend/importing/".format(self.opts.frontend_base_url)
        self.upload_url = "{}/backend/import-completed/".format(self.opts.frontend_base_url)
        self.auth = ("user", self.opts.frontend_auth)
        self.headers = {"content-type": "application/json"}

    def run(self):

        tmp = tempfile.mkdtemp()
        log.info("DistGitImported initialized")
        try:
            while True:
                log.info("1. Try to get task data")
                try:
                    # get the data
                    r = get(self.get_url)

                    # take the first task
                    builds_list = r.json()["builds"]
                    if len(builds_list) == 0:
                        log.debug("No new tasks to process")
                        time.sleep(30)
                        continue
                    task = builds_list[0]

                    # extract data from it
                    task_id = task["task_id"]
                    user = task["user"]
                    project = task["project"]
                    #package = task["package"]
                    branch = task["branch"]
                    source_type = task["source_type"]
                    source_json = task["source_json"]

                    if source_type == 1:  # SRPM link
                        package_url = json.loads(source_json)["url"]
                    elif source_type == 2:  # SRPM upload
                        json_tmp = json.loads(source_json)["tmp"]
                        json_pkg = json.loads(source_json)["pkg"]
                        package_url = "{}/tmp/{}/{}".format(
                            self.opts.frontend_base_url, json_tmp, json_pkg)
                    else:
                        log.error("Got unknown source type: {}".format(source_type))
                        raise Exception("Got unknown source type: {}".format(source_type))

                except KeyboardInterrupt:
                    sys.exit(0)

                except Exception:
                    log.exception("Failed acquire new packages for import")
                    time.sleep(30)
                    continue

                log.info("2. Importing the package: {}".format(package_url))
                try:
                    log.debug("download the package")
                    fetched_srpm_path = os.path.join(tmp, os.path.basename(package_url))
                    try:
                        urllib.urlretrieve(package_url, fetched_srpm_path)
                    except IOError:
                        raise PackageDownloadException

                    # todo: check that obtained file is a REAL srpm
                    # todo  query package name & version and ise real name instead of task["package"]
                    # if fetched file is not a proper srpm set error state
                    name, version = pkg_name_evr(fetched_srpm_path)

                    reponame = "{}/{}/{}".format(user, project, name)
                    log.debug("make sure repos exist: {}".format(reponame))
                    call(["/usr/share/dist-git/git_package.sh", reponame])
                    call(["/usr/share/dist-git/git_branch.sh", branch, reponame])

                    log.debug("import it and delete the srpm")
                    git_hash = import_srpm(user, project, name, branch, fetched_srpm_path)

                    log.debug("send a response - success")

                    # refresh cgit
                    call(["/usr/share/dist-git/cgit_pkg_list.sh", self.opts.cgit_pkg_list_location])

                    # send a response - success
                    data = {"task_id": task_id,
                            "pkg_name": name,
                            "pkg_version": version,
                            "repo_name": reponame,
                            "git_hash": git_hash}
                    self.post_back(data)

                except (PackageImportException, PackageDownloadException, PackageQueryException):
                    log.info("send a response - failure during import of: {}".format(package_url))
                    self.post_back_safe({"task_id": task_id, "error": "error"})

                except Exception:
                    log.exception("Unexpected error during package import")
                    self.post_back_safe({"task_id": task_id, "error": "error"})

                finally:
                    try:
                        os.remove(fetched_srpm_path)
                    except Exception:
                        log.exception("Failed to remove fetched srpm")

        finally:
            shutil.rmtree(tmp)

    def post_back(self, data_dict):
        """
        Could raise error related to networkd connection
        """
        post(self.upload_url, auth=self.auth, data=json.dumps(data_dict), headers=self.headers)

    def post_back_safe(self, data_dict):
        """
        Ignores any error
        """
        try:
            self.post_back(data_dict)
        except Exception:
            log.exception("Failed to post back to frontend : {}".format(data_dict))


def main():
    config_file = None

    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    config_reader = DistGitConfigReader(config_file)
    try:
        opts = config_reader.read()
    except Exception as e:
        print("Failed to read config file, used file location: `{}`"
              .format(config_file))
        # sys.exit(1)
        sys.exit(1)

    logging.basicConfig(
        filename=os.path.join(opts.log_dir, "main.log"),
        level=logging.DEBUG,
        format='[%(asctime)s][%(levelname)s][%(name)s][%(module)s:%(lineno)d] %(message)s',
        datefmt='%H:%M:%S'
    )

    logging.getLogger('requests.packages.urllib3').setLevel(logging.WARN)
    logging.getLogger('urllib3').setLevel(logging.WARN)

    log.info("Logging configuration done")
    log.info("Using configuration: \n"
             "{}".format(opts))
    importer = DistGitImporter(opts)
    try:
        importer.run()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
