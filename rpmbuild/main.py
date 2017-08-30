import re
import os
import sys
import argparse
import subprocess
import requests
import json
import munch
import logging
import tempfile
import ConfigParser
from jinja2 import Environment, FileSystemLoader

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin


file_handler = logging.FileHandler(filename="builder-live.log")
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]
logging.basicConfig(level=logging.DEBUG, handlers=handlers)
log = logging.getLogger(__name__)


def run_cmd(cmd, cwd=".", raise_on_error=True):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str workdir: In which directory to execute the command
    :param bool raise_on_error: if PackageImportException should be raised on error

    :raises PackageImportException
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RuntimeError(str(e))

    result = munch.Munch(
        cmd = cmd,
        stdout = stdout.strip(),
        stderr = stderr.strip(),
        returncode = process.returncode
    )
    log.debug(result)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


class DistGitProvider(object):
    def __init__(self, source_json, workdir=None):
        self.clone_url = source_json["clone_url"]
        self.branch = source_json["branch"]
        self.workdir = workdir

    def run(self):
        repodir = os.path.join(self.workdir, "repo")
        result = self.clone(repodir)
        log.info(result)

        cfg = self.render_rpkg_template()
        log.info(cfg)

        config_path = os.path.join(self.workdir, "fedpkg.conf")
        f = open(config_path, "w+")
        f.write(cfg)
        f.close()

        if self.branch:
            self.checkout(self.branch, repodir)

        module_name = self.module_name(self.clone_url)
        result = self.produce_srpm(config_path, module_name, repodir)
        log.info(result)

    def clone(self, repodir):
        cmd = ["git", "clone", self.clone_url, repodir]
        return run_cmd(cmd)

    def checkout(self, branch, repodir):
        cmd = ["git", "checkout", branch]
        return run_cmd(cmd, cwd=repodir)

    def render_rpkg_template(self):
        jinja_env = Environment(loader=FileSystemLoader("."))
        template = jinja_env.get_template("fedpkg.conf.j2")
        parse = urlparse(self.clone_url)
        distgit_domain = parse.netloc
        return template.render(distgit_domain=distgit_domain, scheme=parse.scheme)

    def module_name(self, url):
        parse = urlparse(url)
        return re.sub(".git$", "", re.sub("^/c?git/", "", parse.path))

    def produce_srpm(self, config, module_name, repodir):
        cmd = ["fedpkg", "--config", config, "--module-name", module_name, "srpm"]
        return run_cmd(cmd, cwd=repodir)


def main():
    parser = argparse.ArgumentParser(description="Runs COPR build of the specified task ID,"
                                                 "e.g. 551347-epel-7-x86_64, and puts results"
                                                 "into /var/lib/copr-rpmbuild/results/.")
    parser.add_argument("task_id", type=str, help="COPR task-id to be built (e.g. 551347-epel-7-x86_64)")
    parser.add_argument("-d", "--detached", action="store_true", help="Run build in background."
                                                                      "Log into /var/lib/copr-rpmbuild/main.log")
    parser.add_argument("-v", "--verbose", action="count", help="print debugging information")
    args = parser.parse_args()

    config = ConfigParser.RawConfigParser()
    config.readfp(open("main.ini"))

    url = urljoin(urljoin(config.get("main", "frontend_url"), "/get-build-task/"), args.task_id)
    response = requests.get(url)
    task = response.json()
    source_json = json.loads(task["source_json"])

    workdir = tempfile.mkdtemp()
    provider = DistGitProvider(source_json, workdir)
    provider.run()


if __name__ == "__main__":
    main()